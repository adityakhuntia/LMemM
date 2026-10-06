# Keyboard and Cursor Timeline Implementation Plan

**Status: CLOSED — all five implementation tasks completed and pushed.** Final product-code verification: 89 tests passed at f148813; README/handover published in 5197c4d. Basic live input/linkage passed; remaining QA is tracked separately below.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Record opt-in, privacy-gated keyboard/cursor summaries and connect them to captures in an inspectable session timeline.

**Architecture:** A pure aggregator reduces permitted events immediately; a separate macOS adapter owns the listen-only event tap and privacy inspection. The tracker coordinates pause/context boundaries, capture linkage and persisted evidence; the existing CLI exposes controls and inspection. Default startup never starts an event tap.

**Tech Stack:** Python 3.11, installed PyObjC Quartz/Cocoa bindings, Carbon secure-input query, local JSON, unittest. One required ApplicationServices PyObjC framework binding was added after installed-API inspection; no external service.

**Spec:** [Approved input timeline design](../specs/2026-10-05-input-timeline-design.md).

## Global Constraints

- Explicit `--input-events` and at least one `--input-app` are required; initial supported allowlist is `com.microsoft.VSCode`. Reject unsupported/browser bundles with an actionable error rather than silently broadening scope.
- Never read characters, clipboard or AX editable values, or persist raw keys/modifiers. The later user-authorized Ctrl+Tab/Cmd+Tab amendment permits only transient Tab/modifier classification; ordinary input stays counts. Do not intercept or synthesize input.
- Require listen permission, Accessibility inspection, known non-secure focus and global secure-input availability; otherwise collect no detail. Default capture retains its existing permission behavior.
- Keep 30 seconds maximum transient context and 24 hours maximum persisted summaries by default; configuration may shorten either. Pause, exclusions and gaps clear ambiguous transient evidence.
- Capture/OCR, existing notes/content, Google Docs identity and old/new memory loading remain compatible. No live input/audio monitoring during automated tests.
- Native adapter callbacks do no OCR, file writes or AppleScript. Persist restrictive local files; plaintext limitations remain documented.

## Review Focus

- Delayed event delivery after an app switch must not assign earlier input to a new app: adapter/context-boundary tests in Task 2.
- Missing AX role or secure-input function must disable detail collection, not assume safe focus: privacy tests in Task 2.
- High-frequency movement or event-tap disablement must produce bounded state and visible gaps: Tasks 1 and 2.
- Delayed OCR after pause/deletion must not recreate deleted evidence or attach it to another context: Tasks 3 and 4.
- Legacy shared items lack complete session-owned evidence; deletion must fail before mutation when safe reconstruction is impossible: Task 4.

## File responsibilities

- `input_events.py`: pure summary aggregation, ordering, bounds and serialization.
- `input_monitor.py`: native permission checks, secure-focus gating, event-tap/run-loop lifetime; no persistence.
- `input_store.py`: summary retention, provenance contributions and safe session deletion.
- `tracker.py`: collector lifecycle, context/capture correlation, pause and evidence contribution hooks.
- `lmemm.py`: opt-in flags, controls, status, event rendering and deletion command.
- `tests/test_input_events.py`, `tests/test_input_monitor.py`, `tests/test_input_pipeline.py`, `tests/test_input_store.py`: behavior and boundaries. Existing tests continue to run.

### Task 1: Pure bounded interaction summaries

**Interfaces:** `Aggregator(session_id: str, anchor_utc: str, origin_ns: int, transient_seconds: float=30, max_summaries: int=256)`; `feed(kind: str, event_ns: int, context: dict, payload: dict) -> None`; `drain(now_ns: int) -> list[dict]`; `clear(reason: str) -> None`. Only an explicit permitted context `{id, bundle_id, window_id}` can enter `feed`.

- [x] Write failing `test_bursts_split_on_inactivity_and_context`: two keys 0.2 seconds apart become one `keyboard_activity` summary with count 2; a context change discards ambiguous pending input; a subsequent key starts a different burst.
- [x] Write `test_pointer_is_coarse_and_schema_has_no_raw_input`: coordinates reduce to a 3×3 window-relative region; output contains only approved fields, no raw positions or key payload. Reject unexpected payload keys.
- [x] Write ordering/overflow/expiry tests: sequence ties deterministic; malformed/backwards time is a gap; more than 256 ready summaries stays bounded; context older than 30 seconds expires with a coverage gap.
- [x] Run `.venv/bin/python -m unittest discover -s tests -p test_input_events.py -v`; confirm missing behavior fails.
- [x] Implement keyboard and scroll bursts with 0.75-second inactivity flush; pointer movement at most one summary per second; clicks finish immediately. Scroll magnitude has small/medium/large buckets; no raw path is retained. Summary schema includes `event_id`, `sequence`, `kind`, context ID, start/end monotonic offsets, UTC times, minimal payload and coverage status.
- [x] Run focused tests, inspect serialized schema and review the deliverable. Commit only this task's files, leaving unrelated staged work untouched.

### Task 2: Listen-only macOS adapter and fail-closed context gate

**Interfaces:** `InputMonitor(aggregator: Aggregator, allowed_apps: set[str], context_provider: callable, on_gap: callable)`; `start(request_permission: bool=False) -> bool`; `stop() -> None`; `set_paused(paused: bool) -> None`; `status() -> dict`. `permitted_context(allowed_apps: set[str]) -> dict | None` reads foreground identity/bounds, AX role/subrole and secure-input state only. Its failure returns no detail context.

- [x] Write failing tests for missing/denied Input Monitoring, unavailable Accessibility, secure role, failed AX inspection, unknown global secure-input state and excluded/browser apps. Assert no event detail reaches the aggregator.
- [x] Write tests for listener disablement, callback exception, bounded event delivery, context changes during inspection and adapter teardown. A fake native API checks listen-only registration and that returned events are unchanged; it must reject calls to character/keycode/value APIs.
- [x] Run `.venv/bin/python -m unittest discover -s tests -p test_input_monitor.py -v`; confirm red.
- [x] Implement the adapter with Quartz bindings and a run-loop source. Callback reduction reads only event type/time, locations for mouse kinds and scroll delta fields for scroll kinds. Key events never query a key field. Keep native references alive through stop; remove/invalidate the source and tap on shutdown.
- [x] Calibrate event timestamps against native uptime plus the session monotonic clock at startup. Reject events whose delivery lag exceeds 100 ms or context is indeterminate; record a coverage gap. Recheck foreground identity around role/bounds inspection. Missing Carbon secure-input query fails closed.
- [x] Permission prompts occur only through explicitly enabled startup, never ordinary capture or tests. Disabled taps clear buffers and report disabled status; recovery requires a fresh permission/context check.
- [x] Run focused tests and review/commit the adapter task.

### Task 3: Tracker integration, captures and pause controls

**Interfaces:** extend `Tracker(every=EVERY, input_apps: set[str] | None=None, input_retention_hours: float=24)`; `set_manual_pause(paused: bool) -> None`; collector enabled only when `input_apps` is nonempty. `InputStore(session_id, root, retention_hours=24)` supplies `append(summaries)`, `link_capture(capture_id, context_id, start_ns, end_ns, item_id=None)`, `invalidate_context(reason)`, `status()` and `close()`; its persistence/reconstruction implementation is Task 4.

- [x] Write failing pipeline tests for default-off, permitted keyboard/click/scroll capture triggers, minimum-gap/backlog behavior, pause/lock/sleep/exclusion/note-panel clearing, and paused pins/notes producing no capture.
- [x] Write delayed-OCR linkage tests: summary/capture IDs are preserved, before-frame age is explicit, a different context cannot become the owner, and closed/deleted sessions cannot receive late writes.
- [x] Run `.venv/bin/python -m unittest discover -s tests -p test_input_pipeline.py -v`; confirm red.
- [x] Integrate lifecycle into `run`, `tick`, `set_flag`, `open_note`, `capture`, `_remember_frame` and `finish`. Drain summaries on the main loop; request `input_activity` through existing debounce when a keyboard/scroll burst ends or click occurs. Pointer movement alone does not trigger screenshots. Keep OCR outside the memory lock.
- [x] Capture metadata records monotonic start/end and summary IDs. Retain confirmed allowed-context app/window transitions without revealing names of excluded apps. Monitoring gaps carry reason/time only, no input/app/window details.
- [x] Add `pause`, `resume`, `status` control commands through a private atomic control file polled on `tick`. `pause` also stops screenshot capture and cancels an open note panel; clear comparison state and active intervals. A stale PID/control file is rejected visibly. No arbitrary signal overload that could interrupt note handling.
- [x] Run focused tests plus existing identity/note/persistence tests. Review and commit the integration task with minimal required store interfaces supplied by Task 4 before declaring its tests green.

### Task 4: Local retention, provenance and safe session deletion

**Files/interfaces:** implement Task 3's `InputStore` in `input_store.py`; `plan_session_deletion(session_id: str, paths: dict) -> dict` returns affected paths, remaining shared contributions and blockers without writes; `delete_session(session_id: str, paths: dict) -> dict` mutates only a validated plan and rejects active sessions. Event file: `data/memory/inputs/<session>.json`, mode 0600 and private parent directory.

- [x] Write failing tests for 24-hour pruning on append/read/startup, permissions, bounded file size and corrupt event stores. A retention setting outside `(0,24]` hours is rejected. Event files may retain coverage counters after detailed summaries expire.
- [x] Write session contribution tests: new sessions record source-owned notes/excerpts and numeric activity/count deltas per item. Deleting one session removes only its evidence and recomputes shared totals, excerpt first/last times and visits from remaining supported contributions. Do not invent a replacement screenshot.
- [x] Write tests for deletion with active OCR, path traversal, missing provenance, legacy shared items, unrelated/replay evidence and interruption. An active tracker session or incomplete reconstruction blocks deletion before modifying any file. A referenced replay copy blocks deletion with its path until explicitly included; do not leave private replay evidence silently behind.
- [x] Run `.venv/bin/python -m unittest discover -s tests -p test_input_store.py -v`; confirm red.
- [x] Implement atomic private writes and session-owned contribution records alongside existing snapshots. Store an immutable baseline for pre-feature legacy item evidence; legacy session deletion is blocked when that baseline cannot be separated. New tracked session deletion can restore the baseline plus remaining supported contributions.
- [x] Deletion validates source metadata and paths confined to `data/`, prepares recomputed memory/session exports, then publishes replacements and removes exclusively owned frames/metadata/input/contribution files. Persist an operation manifest so interruption is detected and safely completed on next load. Never delete a shared screenshot still referenced by retained evidence.
- [x] Run store and pipeline tests; review and commit this persistence task. Task 3 and 4 integration is one execution checkpoint because their interfaces are coupled.

### Task 5: CLI, documentation and end-to-end verification

**Files:** `lmemm.py`, `README.md`, `context.md`, relevant CLI tests. Normal `run.sh start` remains capture-only; document foreground startup for opt-in monitoring.

- [x] Write failing CLI tests for required allowlist, unsupported bundle rejection, `--input-retention-hours` validation, `memory --events` with old/new stores, visible unavailable/paused status, and `delete-session <id> --dry-run` / `--confirm <id>` (confirmation must exactly match the planned inactive session).
- [x] Implement startup arguments `--input-events --input-app com.microsoft.VSCode`, optional shortened retention, and event rendering independent of OCR activity. Preserve `memory --content` and notes. Display keyboard activity without claiming typed content or shortcuts; mark uncertain navigation and coverage gaps explicitly.
- [x] Run `.venv/bin/python -m unittest discover -s tests -v` with macOS graphics-service access for existing native OCR tests. Native adapter tests remain permission-free and do not install a real listener.
- [x] Basic user-scripted live acceptance: after permissions and the Electron AX repair, VS Code retained keyboard/cursor/scroll/click summaries with capture/item links. See the closure evidence below.
- [ ] Follow-up QA-1/QA-2: repeat the latest shortcut/timing cleanup and the complete exclusion/pause/note/lock/sleep lifecycle script; basic recording is not proof of the full sequence.
- [x] Review whole change using superpowers' code-review step; fix concrete important findings, rerun relevant checks, then update README/context with implemented versus pending behavior and commit task-scoped files. Do not push without user instruction.

## Execution and time boundary

Recommend **Native** execution: implement in this session, then one independent whole-change review. The tasks share clock/context/store interfaces, so serial execution is simpler and avoids parallel integration overhead. This complete privacy/control increment may exceed the earlier remaining one-hour window, especially deletion/provenance reconstruction; do not silently drop these requirements or enable a partial monitor. If the user needs a hard shorter deadline, obtain approval for a reduced slice before product-code changes.

## Self-review

Spec coverage: Tasks 1–2 cover collection/privacy/aggregation; Tasks 3–4 cover linkage, controls, retention and deletion; Task 5 covers visible output and live/automated validation. Review Focus cases are assigned above. Interfaces and defaults agree across tasks. Remaining live permissions are explicit external prerequisites, not proof supplied by unit tests.

## Execution result and closure

All five implementation tasks are **closed** on `feat/input-timeline`. Independent
reviews completed and important findings were fixed with regression coverage.
The final full suite at f148813 passed **89 tests** (macOS graphics access);
automated input tests installed no real listener or microphone. User-driven live
session 20261005-220033 retained 6 keyboard bursts / 56 accepted presses,
4 movement summaries, 3 clicks and 3 scroll summaries. 11 summaries linked to
captures/items, 8 with before-images. False ordering gaps found in that run were
subsequently repaired; the repair and new shortcut recognition need live repeat.

Implementation was pushed through f148813 and README/handover through 5197c4d.
It is not merged into main. The remaining open checkbox is follow-up acceptance,
not an incomplete implementation task; do not rerun finished implementation work.

## Follow-up queue (not implementation blockers)

- [ ] QA-1: latest navigation/timing live repeat, including reverse shortcuts and switcher coverage limitations.
- [ ] QA-2: full privacy/lifecycle live script including pause, note panel, exclusions, lock/sleep/resume.
- [ ] QA-3: real Google Docs two-session identity acceptance.
- [ ] QA-4: live speech/hotkey accuracy and permission behavior.
- [ ] QA-5: longer/multi-display sessions.
- [ ] INT-1: feature review and merge into main when requested.

The canonical status/evidence and recommended next geometry increment are in
[context.md](../../../context.md). Existing scope boundaries still apply; closing
this plan does not authorize all-app input, browser monitoring or semantic recall.
