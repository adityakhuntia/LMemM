# Keyboard and cursor timeline — first increment

Status: **CLOSED — implementation/review complete and pushed** through f148813; README/handover published in 5197c4d. Basic live input/capture linkage passed after the AX repair. Latest shortcut/timing and full lifecycle acceptance remain follow-up QA, not unfinished implementation.

## Intent and acceptance

The user moved keyboard/cursor integration ahead of capture-quality repair. The goal is a timestamped account of interactions connected to screenshots: keyboard activity, pointer actions, scrolling and context transitions. The first increment should improve evidence without pretending to know user intent or storing what the user types.

Success: an explicitly enabled, permitted VS Code session records bounded interaction summaries and links them to captures. Denied permission, pause, secure input, an excluded foreground app, or the note panel produces no detailed interaction records. A scripted edit/scroll/click/app-switch sequence can be inspected through the existing CLI. No key characters, keycodes, modifiers, clipboard contents, or editable-field values reach stored records.

## Approaches and selection

1. Extend existing input-age/pointer polling: least code, but misses interactions and cannot accurately timestamp bursts. Keep as the permission-denied fallback, not the claimed event integration.
2. Listen-only macOS event tap with immediate aggregation: recommended. Supplies actual event times while allowing a deliberately small retained schema. Reuse the existing capture/CLI and keep the collector separate from OCR.
3. Per-app extensions: stronger app semantics and more reliable document/tab IDs, but unsuitable as the first cross-app interaction increment. Add adapters later.

Installed Quartz bindings expose the needed event-tap, permission, timestamp and run-loop APIs. That verifies API availability, not granted permission or live operation. Apple reference: https://developer.apple.com/documentation/coregraphics/cgeventtapoptions/listenonly

## Collection and permissions

- Add `--input-events` opt-in and a required explicit app allowlist, e.g. `--input-app com.microsoft.VSCode`. Normal startup remains capture-only. The first live target is VS Code; browser input remains excluded in this first increment because reliable private-tab context requires additional work. Existing browser screenshot behavior is not newly validated by this feature.
- Use an annotated-session `CGEventTap` with `listenOnly`; never alter, suppress or synthesize events. Handle Input Monitoring access explicitly; lack of access leaves the existing capture flow working and clearly reports collector unavailability.
- Read only key-down occurrence, mouse action type, pointer position, scroll deltas and event target-process metadata needed for attribution. Never extract characters, clipboard or editable AX values. Ordinary keyboard activity does not inspect keys; the authorized navigation amendment below narrowly permits transient modifier/Tab classification without raw storage. Treat a key burst as keyboard activity, not proof of typing text or a specific shortcut.
- Accessibility inspection reads focused element role/subrole and window context; the implemented VS Code compatibility layer also requests/restores its documented AXManualAccessibility flag on the main loop; secure-field detection and global secure-input checks gate detail collection. Missing required inspection access or indeterminate protection state disables detailed collection. No root or permission bypass.
- The callback does minimal reduction/enqueue work; OCR, file writes, AppleScript and interpretation run elsewhere. Keep the queue bounded; overflow produces an explicit gap rather than silent time extrapolation.

## Aggregation and context

- Keyboard bursts retain start/end and event count; split after a short inactivity interval or foreground-context change. Pointer motion retains only a coarse start/end region and movement/drag summary, not each sampled coordinate. Clicks retain coarse location and button category. Scrolls retain direction and coarse magnitude.
- Use monotonic event offsets plus one UTC session anchor and sequence numbers. A burst carries both start/end times. The native event timestamp is converted consistently; screenshot timestamps describe collection, not OCR completion.
- Context is a session-scoped identifier for permitted app/window. Validate context before attribution and persistence. Discard ambiguous buffered details on context changes, permission/listener gaps, secure input, pause, lock, sleep, exclusions and note-panel display. Never attach old events to the new foreground item.
- Existing app/window notifications can confirm transitions. A window disappearing from polling is only “no longer visible,” not a confirmed close. Do not label a key burst as Cmd-Tab or a pointer action as a confirmed tab switch without corresponding state evidence. Browser-tab attribution is a later extension.
- Immediately aggregate into bounded state; no persistent raw-event journal. Candidate bounds: 30 seconds of transient context and 24 hours of persisted summaries. Make effective limits configurable and report discarded/expired evidence explicitly.

## Capture linkage and output

- End-of-burst, clicks and scroll completion can request a debounced capture through the existing queue; do not capture each event. Keep timer fallback and existing minimum-gap/backlog safeguards.
- Persist permitted summary records under the session with event IDs, times, context ID, minimal payload, and links to capture IDs. A before-capture reference includes its age; it must not imply an immediate before/after pair if no recent permitted frame exists. Capture results link to memory items after resolution.
- Add `memory --events` output: timestamped “keyboard activity”, “pointer moved”, “click”, “scroll” and confirmed app/window transitions. Include collector status and coverage gaps. Keep these observations distinct from inferred OCR activity labels and user notes.
- Show recording state at startup and in CLI status, with a global pause/resume shortcut or signal-based CLI control that also pauses screenshot capture. Revoke/stop must flush only already-permitted summaries and clear transient details. Add session deletion covering these summaries and linked session evidence; shared item evidence requires recomputation rather than deleting unrelated sessions.
- Apply restrictive file permissions to new event files. Persisted data remains plaintext; no encryption or zero-risk privacy claim. Do not add cloud transport or model calls.

## Files and isolation

- `input_events.py`: pure aggregation/schema and native-event ordering.
- `input_monitor.py`: native event-tap adapter, permission/focus/target gates and explicit start/stop/status.
- `input_store.py`: retention, links, contributions and safe deletion/recovery.
- `tracker.py`: opt-in lifecycle, context/privacy gates, pause handling, capture triggers and late capture/item linkage.
- `lmemm.py`: opt-in flags, event inspection and pause/resume controls.
- Tests separate pure aggregation, timestamp/context boundaries, native adapter permission/lifecycle behavior and tracker persistence. Existing content, notes, document identity and both old/new memory formats must remain working.

## Verification

Test event order, burst splitting, bounded buffers, absent forbidden fields, pointer coarsening, exclusion/secure-input/pause/lock boundaries, callback disablement, denied permissions, capture linkage after delayed OCR and retention/deletion. Run the complete existing suite. Validate live only after the user explicitly enables monitoring and grants the macOS permissions.

Scripted live check: edit VS Code, scroll, click between panes, switch to an excluded app, return, open/cancel the note panel, pause/resume and stop. Compare summaries with the user-observed sequence and confirm excluded intervals leave no detailed trail. Report permission limitations and unsupported browser/tab/close semantics separately.

## Scope boundary

Do not fold semantic recall, raw text logging, all-app browser monitoring, window-close inference, a full SQLite migration, or autonomous decisions into this increment. The collector improves observed interaction evidence; capture geometry and activity attribution defects remain subsequent work. If this privacy/control scope exceeds the remaining time budget, deliver a smaller reviewed first slice rather than silently enabling an incomplete monitor.

## Authorized navigation amendment — 2026-10-05

The user requested navigation recognition and clarified Ctrl+Tab / Cmd+Tab (Shift
reverse). The adapter may transiently inspect modifier masks and Tab identity for
these two shortcut families only. Persist classified action/direction/step counts,
never raw keycodes/modifiers or characters. Counts cover accepted permitted focus
and may omit switcher-owned input; do not equate them with window list distance.
Observed transitions may link after a shortcut, but correlation must not cross
pause/security gaps or overwrite an earlier confirmation. Retain original
permission, focus, target-process, delay and retention boundaries.

## Closure record — 2026-10-05

- [x] Design/Native execution approved; first input increment implemented.
- [x] Aggregation, adapter, tracker, store, CLI, pause/retention/deletion delivered.
- [x] Independent reviews completed; important findings repaired with regressions.
- [x] VS Code Electron focus blocker diagnosed and repaired; basic live recording/linkage passed.
- [x] Authorized navigation amendment and false ordering repair implemented/tested.
- [x] Final product-code suite: **89 tests passed**; feature branch pushed.
- [x] README and HANDOVER.md published.

Follow-up acceptance remains open: [context.md](../../../context.md) QA-1 through
QA-5. Main-branch merge is INT-1. Capture geometry, authored-text quality, browser
adapters, semantic recall and agent APIs are later increments, not hidden tasks
inside this closed implementation. Full privacy/complete navigation coverage is
not claimed by closure.
