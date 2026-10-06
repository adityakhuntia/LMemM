# LMemM — current project context

Last updated: 2026-10-05, America/New_York, after implementing the approved opt-in keyboard/cursor timeline on `feat/input-timeline`. Runtime observations below are historical snapshots, not current live status. Semantic recall and shared agent memory remain proposed.


## Current input timeline — implemented 2026-10-05

- Working branch: `feat/input-timeline`; implementation committed locally with its content/identity/dictation dependencies; last reviewed upstream commit remains `df94289`. No push or merge performed. Existing identity/content/dictation fixes remain integrated. Do not reapply the recovery stash.
- Default startup is capture-only. Explicit `--input-events --input-app com.microsoft.VSCode` enables the listen-only annotated-session event tap. VS Code is the only supported input app. Input Monitoring and Accessibility are required; unknown secure-input/focus/target-process state fails closed.
- Keyboard counts, coarse cursor movement/drag/click regions, scroll buckets, allowed-context transitions and coverage gaps carry session monotonic offsets, UTC timestamps and event IDs. No characters, keycodes, modifiers, clipboard or editable AX values are read. Event target process metadata plus verified context boundary times reject ambiguous attribution.
- Flow: **permitted native event → immediate bounded summary → timestamped session input store → debounced settled capture → OCR/content/activity → memory item link**. Timer capture remains. A prior permitted frame has an explicit age; context boundaries prohibit cross-boundary linking. These observations do not establish shortcuts, tab intent, window closure or authored text.
- `status`, `pause`, `resume` use private PID-scoped control/status files. Pause stops captures, clears transient input/comparison intervals and cancels notes. Resume retries disabled/unavailable collectors with fresh checks. Closed stores reject late OCR writes.
- Input stores: `data/memory/inputs/<session>.json`; bounded source copies: `inputs/frames/<session>/`. RAM context max 30 seconds; detailed disk retention max 24 hours, configurable shorter, plus 4,096-record cap with loss counters. All-session pruning runs at startup, every minute while running, and on inactive event inspection. Stopped processes do not erase on a wall-clock schedule; the next startup/read enforces expiration.
- Source-owned notes/excerpts, activity deltas and observed metadata live in `contributions/<session>.json`; baseline preserves pre-feature evidence. Snapshot integrity uses hashes rather than duplicate private content. Safe deletion rebuilds shared memories, prunes owned evidence and recovers interrupted manifests before loading memory. Active trackers, legacy provenance gaps, replay references, external changes and shared source screenshots block deletion before mutation.
- **79 tests passed** in the final full macOS run. Automated verification covers aggregation, fake native adapter/AX privacy checks, CLI, retention, repeated/interrupted deletion and late OCR, plus existing identity, content, dictation, native speech-policy and real Vision tests. No real event listener, microphone or live deletion was enabled by verification. Native APIs/dependency availability is verified; live permissions and useful event coverage are pending.
- Privacy limit: **the input allowlist does not scope ordinary screenshots**. Existing capture saves entire displays and sampled pointer positions, and OCR/activity can include overlapping windows or the tracker’s logs. New source image copies inherit that exposure, are private plaintext files, and expire with input retention. Redaction/cropping/encryption remain future work.

### Run and validate the first slice

```bash
.venv/bin/python lmemm.py --input-events --input-app com.microsoft.VSCode
# Optional shortened input retention: --input-retention-hours 4
# In a second terminal:
.venv/bin/python lmemm.py status
.venv/bin/python lmemm.py memory 20 --events --content
.venv/bin/python lmemm.py pause
.venv/bin/python lmemm.py resume
# After stopping, preview only:
.venv/bin/python lmemm.py delete-session SESSION --dry-run
```

Restart any old tracker before testing; do not run two concurrently. Grant the launching app Input Monitoring/Accessibility and restart if required. Edit, scroll and click in VS Code; switch to an excluded app and back; open/cancel the note panel; pause/resume; stop. Check event times/counts, explicit gaps, source links and absence of excluded input. Unknown event target metadata may reduce coverage and needs measurement. This check is pending, not a claim that live monitoring works.

### Next implementation order

1. Run the short scripted live check and fix measured coverage/permission defects.
2. Fix foreground-window geometry (Safari toolbar selection, focused dialogs, multiple displays) and restrict saved/processed pixels appropriately.
3. Fix self-observation and authored-text attribution; match edits to permitted focused-region input and retain uncertainty.
4. Add reliable app-specific project/file identity and permitted browser/tab adapters; don't infer close/switch semantics from a click alone.
5. Build evidence-backed project recall: “what did we do here two days ago; what is left?” with explicit notes/tasks/decisions, source links and uncertainty.
6. Expose scoped retrieval/proposal APIs to cooperating AI agents using that same persistent layer. No automatic sharing with every installed agent; hosted-agent disclosure requires a separate boundary.

## Upstream review snapshot (2026-10-05)

- At the initial remote review, GitHub was one commit ahead: **`df94289fa00eab1f0f67d43f9c0e94ac0b392234`**, Aditya, October 4 at 16:42 EDT: “Hotkey dictation onto the current memory entry, neater memory.json and output.” Initially reviewed remotely; now pulled and integrated locally (see current integration below). No commit comments were returned. The following bullets record the original upstream review, not the repaired local behavior.
- Adds Control–Option–N dictation, an editable note panel, `lmemm.py note`, and a compiled Apple Speech helper. User notes attach to the foreground memory and remain distinct from observed activity. Registering this hotkey is not continuous keyboard/cursor integration.
- Changes persistence: readable `memory.json` uses `things`; full internal items move to `.index.json`. Session fields and duration formatting also change. Integration needs explicit schema compatibility/migration checks and must preserve our content history, CLI, and working Vision bindings.
- Adds OCR retries, but does not incorporate our native NSDictionary/official Vision binding/error-tuple repair. Keep the local repair when integrating retries.
- Privacy review: the helper sets `requiresOnDeviceRecognition` only when supported, leaving a possible server-recognition fallback otherwise. Enforce local-only failure with typed-note fallback. Transcript temporary directories are not cleaned up by the current stop path, including cancelled notes; implement cleanup.
- Note attribution needs a guard: known-context matching uses app/window without URL, and a failed fresh capture can fall back to the previous item. Require a verified current context or explicit unresolved/manual association rather than silently attaching elsewhere.
- **Cross-session identity defect reproduced synthetically:** an existing Google Docs item with a stable document reference and prior typing gets a different ID after restarting at a view where the prior text is absent. The same identity rule exists upstream. This is a content-driven split (`ref#2`), not a hash collision or a session ID in the hash. Strong document identity must override missing visible text; sessions should create new episodes on the same entity. Reproduction did not modify captured data.

## Current dictation integration — completed 2026-10-05

- At dictation integration, local `main` and `origin/main` pointed to **df94289fa00eab1f0f67d43f9c0e94ac0b392234**. Fast-forwarded after saving local tracked/untracked work, then restored it and combined README, CLI and OCR conflicts. Those enhancements are preserved in the current feature branch; no push. Recovery stash “LMemM content and stable identity before dictation integration” and backup `/var/folders/8g/bxt6jbv16ql6pz4y7rng36lc0000gn/T/lmemm-before-dictation-bw3n2do8` retained; do not reapply the stash to this integrated tree.
- Control–Option–N and `lmemm.py note` open the native editable dictation panel. Return saves; Escape or the window close button cancels. Speech requires on-device support, with no server-recognition fallback; unsupported/denied recognition leaves typed notes available. Audio is not persisted by this helper.
- Temporary transcripts/errors/control files are removed on close. A helper checks cancellation while permission requests are pending and during recording; closing the panel removes its private directory and signals a running helper. Lock/sleep flags and tracker shutdown cancel an open panel. Current storage remains plaintext local JSON/JPEG; encryption and broader privacy controls are future work.
- Every note begins with a fresh permitted capture; there is no previous-item fallback. Missing/changed post-capture native context or changed browser URL/title/private state rejects it. This verifies sampled context, not an app-provided durable document ID in every app.
- Note saves do not wait on OCR: OCR runs outside the memory lock; pending notes are persisted immediately in session JSON and attached after the exact frame resolves. Failed resolution retains explicit unresolved status. Raw note text is not echoed into live logs.
- Schema version 2 preserves full items/content/notes in `.index.json` and exposes readable content/notes in `memory.json`. Numeric session durations, activity, triggers and item references remain alongside readable fields. Legacy full stores load and migrate on save; corrupt/unsupported stores or readable-only stores lacking the index raise an error rather than being replaced with empty data.
- Preserved stable Google Docs identity, bounded source excerpts, unverified decision quotes, official Vision bindings/native NSDictionary options and NSError tuple handling. Integrated accurate/auto-language/fast OCR retries without reintroducing the original bridge error. CLI supports notes, excerpts and legacy/new sessions.
- **29 tests passed** in the final full macOS run, including actual Vision OCR, native compiled local-only speech policy, OCR retry handling, migration safety, cross-session identity, pending note attachment, nonblocking note saving during worker OCR, context-change rejection and transcript cleanup. Code review found a native context-recheck gap; its failing regression was added and the gap repaired.
- Native note panel smoke test passed typed saving and window-close cancellation with microphone startup disabled. Speech helper compiled and code-signature verification passed. A temporary migration of the existing **17 items** preserved every field; original live memory file was unchanged. No live capture/microphone session was launched during verification.
- Remaining manual validation: restart the tracker, use the hotkey in a permitted document, allow speech/microphone permissions if desired, dictate/edit/save a note and inspect `memory 5 --content`; test cancel and reopen. Real speech accuracy, permission prompts and hotkey operation in daily use are not yet validated. Next work is foreground bounds, activity contamination and time accounting.

## Proposed durable memory and recall direction

The user wants both project recall (“what did we do here two days ago, and what is left?”) and shared persistent context across AI agents. Start with project continuity as the user-facing experience; shared agent access can use the same memory foundation later. These are architectural proposals, not implemented or newly approved feature scope.

- Separate durable **entities** (project/document/chat), time-bounded **episodes** (visits/sessions), source **evidence** (notes, captures, events, approved repository/agent records), and **memories** (decisions, tasks, summaries). A new capture session must not imply a new document.
- Prefer stable source IDs such as document URL IDs and repository/workspace-relative file identity. Record aliases for renames or alternate app views; do not merge unrelated files merely because their titles match. Ambiguous drafts need separate rules and uncertainty.
- Retain provenance, event time, author/source type, and revisions. Distinguish user-declared intent, observed content, and agent proposals. Missing visible text is not evidence a decision or task ceased to exist.
- A project recall request resolves current workspace/project, retrieves the requested time range and linked notes/decisions/tasks, checks available current state, and returns changes, reasons, open work, and a next action with evidence links. Unfinished work needs explicit task/decision evidence; screenshots alone cannot establish intent or completion.
- A versioned local transactional store (e.g. SQLite) with one persistence service is a proposed successor to independently rewritten JSON. Begin with structured filters/full-text search; evaluate embeddings when semantic recall needs them. Preserve exports and migration checks.
- Expose scoped search/context and proposal/write APIs to participating agents, potentially through MCP. Each client must be configured and restricted to permitted projects; installing LMemM does not automatically give every agent shared memory. Treat retrieved text as evidence, not executable instructions. Agent proposals must not silently overwrite user declarations.
- Local storage does not guarantee local inference: an agent using a hosted model may transmit retrieved context. Make that boundary explicit and control what each client can retrieve.
- Recommended order is recorded below. With the user's new one-hour constraint, the stable-identity repair comes first on the existing local tree; dictation integration follows as a separate increment. The eventual acceptance demo should revisit one document/project across two sessions and recover its explicit note plus unfinished next step without duplication.

## One-hour increment proposed on 2026-10-05

**Outcome:** reopening the same identifiable Google document in another capture session updates its existing memory and adds a separate session visit, even if visible content or scroll position changed. This is a bounded repair to the existing identity/persistence flow, not a new memory subsystem. The user approved this design with “go for it”; implementation and automated verification are complete. Live two-session validation is pending.

- Use stable source identity where it is actually available. First scope: Google Docs URL/document ID already extracted by the existing rules. Do not pretend title-derived code-file references or generic draft locations are equally authoritative.
- Stable document references must bypass content-disappearance splitting. Preserve the existing cautious heuristic for ambiguous drafts/untitled contexts. Different document IDs remain separate even when titles match.
- Touch the identity logic in `tracker.py` and reference construction in `understand.py` only if necessary; add focused regression coverage in `tests/`. Keep existing content, timestamps, and session links intact. Do not bulk-merge historical duplicates without a reviewed migration.
- Verify restart/reload with the same document at another scroll position, changed visible text, and a changed title; verify two different document IDs with the same title remain distinct. Include an ambiguous-draft regression and persistence/session-link check.
- Budget target: 10 minutes to pin the failing regression and scope; 20 minutes for the repair; 15 minutes for regression and existing checks; 10 minutes for a user-driven close/reopen capture; 5 minutes for the handoff. These are estimates, not a guarantee. If no live session is available, report automated verification separately.
- Done means one document item survives two sessions, both sessions reference it, and retained content still updates. Existing duplicates may remain until a later safe migration. If the repair reveals a broader identity redesign, stop expanding scope and document it.

### Implemented and verified

- `understand.py` marks real `docs.google.com/document/.../d/<id>` references authoritative, including the `/u/0/` route. Title-only, short placeholder IDs and lookalike/non-Google URLs are not marked authoritative. Existing reference strings and stored IDs are preserved.
- `tracker.py` reuses the latest existing matching document item before applying visible-text heuristics; a previously unseen authoritative reference creates its own item and cannot be aliased to another document merely because text matches. No schema migration, historical duplicate merging or personal capture modification was performed.
- Six new regression tests cover restart, edits, scrolling, rename, distinct IDs with identical titles/text, title-only fallback, reused email draft slots, URL boundaries, and real persistence of two synthetic sessions with updated excerpts and one document item.
- Observed the regressions fail before the repair (duplicate items and distinct-document conflation), then pass after it. **Full suite: 18 tests passed**, including real Apple Vision OCR, with approved macOS graphics-service access. The sandboxed full run aborted at the OCR graphics test; the approved rerun completed normally. `git diff --check` passed.
- Live close/reopen validation has been requested from the user; no new live-session result has been claimed. Restart any existing tracker to load the updated code. Browser URL access is necessary for the authoritative identity path; missing Automation access leaves the title-derived heuristic in place.
- Upstream dictation was subsequently integrated as described below. All local source enhancements, including the identity repair, remain uncommitted.

## Recommended build order after the one-hour increment

Input-timeline spec was approved by the user. The [implementation plan](docs/superpowers/plans/2026-10-05-input-timeline.md) is written and self-reviewed; it is pending user review and execution-method selection under superpowers. Native execution is recommended because the collector/context/store interfaces are closely coupled. No collector code or monitoring has been enabled. Full privacy controls and reconstructable session deletion may exceed the earlier one-hour budget; scope must be explicitly reduced if that deadline remains hard.

**User priority correction:** implement keyboard/cursor integration next, ahead of foreground-quality/accounting repair. Concrete first-increment design: [input timeline spec](docs/superpowers/specs/2026-10-05-input-timeline-design.md), committed alone as **f5661a0** per the superpowers architecture workflow. Local `main` is now one documentation commit ahead of `origin/main` (df94289); implementation enhancements remain uncommitted and nothing was pushed. This is a new collector/timeline subsystem; the written design is approved, the implementation plan awaits review/execution selection, and no monitoring has been enabled. Start opt-in with an explicitly allowed VS Code context, minimal summaries and privacy/permission gates; browser input/tab semantics need stronger context protection before inclusion.

1. **Integrate upstream dictation safely.** Preserve the working Vision fix, excerpts, decision quotes, and CLI; test old/new storage formats and session links. Enforce on-device-only speech with typed-note fallback, remove temporary transcripts, and verify note attribution against current app/window/URL. Do not silently fall back to an unrelated previous memory.
2. **Add privacy controls and minimal keyboard/cursor summaries — next by user request.** Visible state, pause, explicit app allowlist, exclusions, retention/deletion and permission handling; then keyboard bursts without characters, clicks/scroll/brief movement summaries, and confirmed app/window transitions. Correlate them with permitted captures using event timestamps. Browser input and tab semantics follow when private-context gating is reliable. Detailed proposed design and written spec are linked above.
3. **Repair capture quality and accounting.** Fix focused-window geometry, browser body extraction, self-observation, uncertain typing attribution, and pause/idle/shutdown time gaps. Validate with a short scripted session before broader recording.
4. **Build the first project-recall output.** Resolve a current document/project; retrieve a chosen time range; show what changed, explicit reasons/decisions, evidenced unfinished work, and a next action with source/time links. Start with deterministic retrieval and the existing CLI before adding a new UI or semantic model. State unknown completion clearly.
5. **Strengthen the persistent memory foundation.** Introduce versioned entities, episodes, evidence, decision/task revisions, project links, safe migrations, and transactional storage when the recall increment establishes requirements. Add full-text search first; evaluate embeddings against real recall failures.
6. **Expose scoped cross-agent memory.** Provide configured clients with project-limited search/context and attributed proposals/writes, potentially via MCP. Preserve user declarations, handle conflicting revisions, treat retrieved text as data, and make hosted-model transmission boundaries explicit.
7. **Expand the companion experience.** Add contextual recall UI, reminders/proactive resurfacing, and longer-session evaluation after retrieval quality and privacy controls are demonstrated.

## Latest short live check (2026-10-04, 12:24 EDT)

- Fresh session `20261004-122154` persisted **104 seconds, 10 touched items, 13 timeline entries**. Main store now contains **17 items and 2 sessions**. No tracker PID file was present at inspection.
- Nine touched items contain **21 excerpts** in total. All timeline item references and representative screenshots exist. Every timeline activity sum matches its duration, and excerpt count/length limits hold.
- Content capture is working for code and an AI conversation, and revisits to README stay attached to one item. This was a short smoke check, not validation of long-session behavior or decision detection; no decision quotes were captured.
- **Confirmed browser excerpt defect:** Safari metadata gives a foreground region only about 11.5% of display height. The inspected screenshot contains a full webpage, but retained excerpts contain tabs/bookmarks and omit the page body. Foreground-window selection/bounds needs investigation before browser content quality can be called correct.
- **Activity contamination:** VS Code activity records include the tracker's own terminal output and unrelated tab-label text in the typing category. Visible screenshot/retained text confirms self-observation; labels should not yet be trusted as precise authored-text attribution.
- No code or captured data changed during this check. Older verification counts below describe the pre-session state.

## Repository and integration state

- Repository: https://github.com/adityakhuntia/LMemM
- Before dictation integration, local `main` and `origin/main` were at **`3ec423e4b2015612e80843ccfd9b3ffb5db681d1`**: “Activity tracking from screen changes, one rule for same-vs-new things.” Author: Aditya Khuntia; October 4, 2026, 07:30 EDT.
- Pulled with `git pull --ff-only origin main`, advancing from `a4829db`.
- Preserved the local Vision fix, content excerpts, decision quotes, CLI changes, and tests. Resolved overlaps in `README.md`, `lmemm.py`, `requirements.txt`, and `tracker.py` by combining both behaviors.
- The integrated local enhancements remain **uncommitted**; being current with GitHub does not mean those enhancements are published there. No push was performed.
- Recovery copies retained: Git stash named “LMemM local OCR fix and content memory before upstream integration”; filesystem backup `/tmp/lmemm-before-pull-20261004-120932/`. Do not apply this stash again to the integrated tree.

## Product direction and user decisions

LMemM aims to be a second memory for digital work: **Capture → Understand → Remember → Resurface**. `ProdIdea.md` describes an ambient Mac companion with voice capture, contextual memories, decisions, reminders, search, and proactive recall.

The user asked to fix the nonworking prototype, then selected **remember meaningful content and decisions** as the next increment. They approved local, bounded, deduplicated foreground excerpts with source/time attribution and explicitly worded decision quotes. These are implemented as evidence retention, not inferred semantic understanding. The user subsequently requested pulling the upstream commit and preserving an accurate handoff of the combined system.

The next requested direction is to fix browser bounds and activity contamination, then correlate screenshots with keyboard activity, pointer actions/movement, and app/window/tab transitions on a timestamped timeline. The purpose is to reconstruct a logical sequence of work while minimizing sensitive input collection. This request updates the handoff and proposed approach; it does not enable a new global input monitor.

## Current flow

1. **Observe the Mac (`tracker.py`).** App-switch notifications plus window/title polling trigger captures; a timer samples the same window every 5 seconds. Debounce is 1 second (up to 3), polling 0.5 seconds, minimum normal capture gap 2 seconds. Idle over 60 seconds, lock, sleep, and display sleep pause capture; sensitive app/site/title checks can skip it.
2. **Capture context.** Screenshot the display containing the foreground window, downscaled to a 1280-pixel long edge. Save app/window/browser URL, normalized foreground-window region, input recency (seconds since keypress, scroll, click), and pointer position. No actual key values are collected.
3. **Compare pixels (`activity.py`).** In the background worker, compare against the prior frame when its app/window/URL signature matches. If changed cells fall below the threshold, reuse the previous OCR and activity description. Other captures run full-image OCR. This optimization is threshold-based, not exact image equality.
4. **Read and label (`resolver.py`, `understand.py`).** Apple Vision reads text, rectangles, and scene labels locally. Layout/entity heuristics classify screen objects. Per-app rules describe the apparent task and target: draft, document, code file, chat, page, etc.
5. **Resolve item identity (`tracker.py`).** Verified Google Docs URL IDs now dominate visible-text heuristics: revisits reuse the same item, and distinct IDs stay separate even when visible text matches. Other contexts still match app/kind/reference plus previously typed text, preserving some title/URL changes or splitting reused draft locations. Items with receiving activity are protected from this splitting. Other apps still rely on heuristics rather than authoritative IDs.
6. **Estimate activity (`activity.py`).** Combine visual changes, scrolling, input ages, and pointer context into typing, reading, receiving, or focus. Newly arrived screens do not contribute text to an attributed activity. Track seconds and at most 15 recent text lines per category, plus the predominant activity (`mostly`).
7. **Retain observed content (`memory_content.py`).** Independently keep readable OCR lines within recorded foreground-window bounds, excluding recognized UI chrome and low-confidence lines. Keep up to 12 distinct excerpts of up to 3,000 characters per item. Each retains app/window/URL and first/last seen. Repeated normalized text updates recency without duplicating it. Explicit phrases such as “We chose …” become **unverified decision quotes**, not claims about the user's intent or authorship.
8. **Persist and inspect.** Write full schema-versioned items to `.index.json`, a readable `things` projection to `memory.json`, and compatible numeric/readable session timelines. Dictated/typed notes remain separate from observed content. Retain one representative screenshot per item and delete redundant/replaced frames during normal processing. New excerpt text refreshes the screenshot even when the item title is unchanged. `memory` displays items, activity totals, and the latest timeline; `memory --content` additionally displays source-attributed excerpts and decision quotes.

The two text streams are intentionally distinct: `activity` estimates what changed while doing something; `content` records what was visibly observed. Existing text can be kept as an observed excerpt without claiming the user typed it.

## Files and data

| File | Role |
| --- | --- |
| `lmemm.py` | CLI: start, `--every`, `pin`, `memory [N] [--content]`, `peek`. |
| `tracker.py` | Events, capture metadata/filters, worker, item identity, activity/content integration, persistence. |
| `activity.py` | Grayscale screenshot differencing, changed regions, scroll estimation, activity classification. |
| `resolver.py` | Apple Vision OCR/geometry/scene labels; standalone frame processing, annotations, reports. |
| `understand.py` | App/site activity descriptions and reference construction. |
| `memory_content.py` | Foreground excerpts, deduplication, bounded history, explicit decision quotes. |
| `run.sh` | Background process management, status, logs, memory/pin forwarding. |
| `logger.py`, `peek.py` | Legacy fixed-interval capture and retained-frame inspection. The legacy logger lacks the tracker's sensitive-content filters. |
| `tests/` | OCR integration, activity classification, capture metadata, content retention, persistence, and CLI tests. |
| `README.md`, `ProdIdea.md` | Current usage and longer-term product vision. |

- `data/<timestamp>.jpg` / `.json`: screenshot and capture metadata.
- `data/memory/.index.json`: authoritative schema-versioned cross-session `items` array containing identity, selected state, timestamps, activity, screenshots, notes and content history.
- `data/memory/memory.json`: readable schema-versioned `things` projection with observed content and `your_notes`. Before migration the existing live file still has the legacy full `items` layout; the next real save performs the migration. Keep both files in backups.
- `data/memory/sessions/<session>.json`: ordered visits, linked item IDs, activity/time summaries.
- Writes use temporary files followed by atomic replacement. Older memory items get empty activity defaults when loaded; old content-free items still load normally.
- `data/objects/`, `data/annotated/`, and `data/report.html` are standalone resolver outputs, not automatically produced by the tracker.
- `data/`, `.venv/`, logs, PID files, and Python caches are Git-ignored. Do not put private OCR or activity contents in this handoff.

## Verified state

- Python 3.11.5 in `.venv`; PyObjC Cocoa/Quartz/Vision/CoreML 12.2.2; NumPy 2.4.6 and Pillow 12.3.0 installed. `pip check` reports no broken requirements.
- **12 tests pass** after upstream integration. Coverage includes real generated-image OCR and decision extraction, invalid-image errors, four activity categories, no attribution on arrival, unchanged-image OCR reuse, capture geometry/input metadata, bounded/deduplicated excerpts, persistence/reload, screenshot refresh, and combined CLI output.
- Combined pipeline replay: **41 frames, 0 errors, 7 items, 12 timeline entries, 7 representative images**, mean processing time about **0.299 seconds/frame**. Validation output: `data/replays/20261004-121803/`; original frames and main memories were left unchanged by this replay.
- These old frames lack input-recency/pointer/window-region metadata. The replay verifies execution and persistence, not accurate typing/receiving classification or new foreground excerpts. Tests cover those behaviors using controlled inputs; a fresh real session is the next quality check.
- After the subsequent short live run, the main store contains **17 items and 2 sessions**, including the 7 earlier recovered items. The fresh session has 10 touched items and 13 timeline entries. All **41 original pre-fix captures** remain available. Recovery deliberately preserved originals, so raw frame count exceeds item count.
- No `.lmemm.pid` file was present at the latest check. No new long-running capture process was launched during integration.

## Original failure and repair

The first run captured 41 frames between 13:30:30 and 13:33:36 on October 3 but produced no memory JSON. Four images were visually inspected; all 41 decoded at 1280 × 831. Real windows and readable text were present.

The captured terminal showed repeated `NSInvalidArgumentException - key does not exist`. Saved-frame replay reproduced it in Vision's request-handler initialization. The local fix uses native `NSDictionary` options, imports the official PyObjC Vision bindings, and handles `(success, error)` explicitly. The upstream activity commit did not include this fix, so it has been retained in the integrated tree.

Initial successful replay output remains at `data/replays/20261004-031649/`; its recovered memory/session JSON was copied into the previously empty main store before this pull.

## Limitations that still matter

- Activity labels, item identity, and decision-phrase detection are heuristic. A VS Code Welcome tab can still be called “Editing Welcome.” Recognized receiving activity is not proof that another person authored text.
- Screenshots cover an entire display. Sensitive checks use foreground context. Excerpts filter to the foreground window's rectangular region, but overlapping windows or misclassified controls can contaminate them. Upstream activity analysis still uses full-display pixels/OCR, not that excerpt filter.
- Small changes below the pixel threshold can reuse stale OCR and delay recognition of new content.
- Missing browser Automation access reduces URL/context quality. Three original frames lacked window titles.
- Historical frames without window geometry produce no new content excerpts. Only visible text is available; long documents/chats are not fully ingested.
- Decision quotes are English phrase matches and may be someone else's words or an AI response. There is no inferred intent, reasoning, semantic summarization, or verified decision ownership.
- Excerpts and activity text are bounded histories; old screenshots are replaced. This is not a complete content archive.
- Time accounting remains approximate: idle/skipped intervals can inflate total duration or inter-item gaps; same-item activity deltas are capped at three capture intervals. Total seconds and activity totals can diverge. Shutdown does not explicitly add the final interval.
- `run.sh status` counts memory JSON files, not items, and its process probe can be denied in an agent sandbox. Use the memory CLI/JSON to inspect actual items.
- Hotkey voice/typed-note capture is now integrated; live speech permission/accuracy validation remains pending. No ambient recall UI, semantic search, reminders, or proactive recall exists yet. `pin` remains a CLI signal-based screenshot request.

## Next implementation steps — ordered

The one-hour identity increment and build order above are the current priorities. The following list expands the capture-quality and event-timeline phases; it is not a separate competing roadmap.

1. **Fix foreground-window selection and geometry.** Investigate why Safari selects a roughly 11.5%-height toolbar window. Prefer the actual focused window via Accessibility where available; validate CoreGraphics candidates rather than assuming the first or largest window is correct. Preserve dialogs as legitimate focused windows. Align coordinates across displays and apply the same valid region to OCR content and activity comparisons. Check browser body text, popups, and multi-display placement.
2. **Fix self-observation and authored-text attribution.** Exclude the tracker's own log/inspection output from activity evidence, including the VS Code terminal pane when identifiable. Filter tab bars/navigation and require a text edit within the focused editable region plus temporally matching keyboard activity before labeling text as typed. If focus cannot be resolved, retain observed text separately and mark attribution uncertain. New text appearing without input can be animation, loading, or program output; it is not necessarily an incoming message.
3. **Add privacy controls, then an opt-in event collector.** Provide a visible recording state, immediate pause, per-app/site exclusions, content-capture settings, retention settings, and session deletion before enabling richer monitoring. Use a read-only event listener; aggregate signals immediately and avoid raw input storage. Permission denial, listener disablement, and secure-input gaps must be visible and supported without breaking capture.
4. **Build the shared timeline and event-triggered capture.** Record event time at collection, associate it with foreground context, and link it to before/after screenshot evidence. Use app activation and focused-window lifecycle signals plus browser URL/title checks to confirm navigation. Debounce/batch events rather than screenshot every keystroke or mouse move. Preserve the existing periodic capture fallback. Close active intervals on pause/idle/lock so gaps do not inflate time.
5. **Validate the story against a short scripted real session.** Type/edit in a document, scroll, switch apps with Cmd-Tab (the macOS equivalent of Alt-Tab), change tabs by pointer and keyboard, close a window, and revisit an item. Check timestamps, window identity, excerpt quality, duplicate handling, and inferred-versus-confirmed labels. Also verify excluded/private contexts leave no screenshot, OCR, or detailed input trail. Long-session validation follows this short check.

## Proposed input/event design and privacy boundaries

The broader design below remains a roadmap. The implemented first slice is the opt-in, VS Code-only summary collector described above; ordinary capture still samples input ages and pointer position. Browser navigation semantics, focused-window lifecycle observation, redaction and shared agent recall are future work.

### Collect the minimum evidence needed

| Signal | Use in understanding | Proposed retained form |
| --- | --- | --- |
| Keyboard activity | Detect typing bursts and relate them to focused-region edits | Burst start/end and count; no characters, Unicode strings, per-letter keycodes, or raw key sequence. |
| App activation | Confirm the foreground app changed | Time, context IDs, source/destination app. A preceding keyboard burst suggests keyboard navigation but does not prove Cmd-Tab. |
| Window focus/lifecycle | Distinguish switching, opening, and closing windows | Confirmed focus/create/destroy events and window IDs. Poll-only disappearance is “no longer visible,” not automatically “closed.” |
| Tab/page navigation | Confirm a tab/URL/title change after a click or keyboard action | Before/after context references and event times. Prefer sanitized URLs; query/fragment text can contain secrets. |
| Click/drag/scroll | Explain navigation or view changes | Time, action type, coarse location or non-text UI role, scroll direction/range; no unrestricted UI value/clipboard reads. |
| Pointer movement | Relate a hover, click, or drag to the changed region | Brief movement summaries/end region, not a permanent high-frequency path. Exact positions may be used transiently for hit-testing. |
| Screenshot/OCR | Establish visible before/after evidence | Cropped/masked permitted region, bounded excerpts, capture interval, and links to event IDs; governed by explicit content-capture settings. |

If exact navigation shortcuts become necessary later, classify a small explicit allowlist transiently and discard raw keycodes immediately. Do not add arbitrary shortcut logging or claim shortcut identity from input-age counters. The first increment should infer navigation from confirmed state changes without storing key values.

### macOS mechanisms to evaluate

- Keep NSWorkspace app activation notifications. Evaluate Accessibility focused-window/element notifications for geometry, focus, and lifecycle without reading editable field values. AX support varies by app; retain a labeled polling fallback.
- Evaluate a session-level `CGEventTap` with `listenOnly` for input events. Keep callbacks lightweight: reduce to event metadata, enqueue, and return; OCR and interpretation remain off the callback thread. Never intercept, suppress, or synthesize user input.
- Global listening and UI inspection require explicit macOS permission handling. Apple describes Input Monitoring for listen-only input observation and Accessibility for relevant UI/control access. Verify required permissions on the supported macOS release; degrade gracefully when access is denied. Do not run as root or try to bypass permission checks.
- References: [Apple event-tap options](https://developer.apple.com/documentation/coregraphics/cgeventtapoptions/listenonly), [app activation notifications](https://developer.apple.com/documentation/appkit/nsworkspace/didactivateapplicationnotification), [Apple's macOS security and input-monitoring explanation](https://developer.apple.com/videos/play/wwdc2019/701/).

### Timestamping and evidence correlation

- Use one session clock based on monotonic time for ordering and elapsed durations, with a UTC wall-clock anchor for display/export. Use sequence numbers for ties. Preserve actual event times even when the OCR worker runs later.
- A proposed event has `session_id`, `event_id`, `sequence`, `monotonic_offset`, `wall_time_utc`, `kind`, `context_id`, a minimal payload, and privacy/availability status. Typing/movement bursts have start/end offsets rather than storing each constituent event.
- A capture records its start/end time and the events it brackets. Link event summaries to the last permitted screenshot and a subsequent settled screenshot; an older “before” image must be labeled with its age.
- Context changes split input bursts so typing in app A cannot be assigned to app B. Clear pending detail and comparison state on blocked contexts, pause, sleep, lock, and monitoring gaps. Do not extrapolate unknown intervals into authored activity.
- Derived story entries keep source event/capture IDs and distinguish observation from inference. Example: “Keyboard activity, then app A → app B” is evidence; “Cmd-Tab” is only confirmed when that shortcut is explicitly observed under the allowed policy. Likewise a click followed by a new URL suggests navigation, not a proven decision or intent.
- Start with deterministic reconstruction. A later summarizer, if added, must consume permitted evidence only and preserve attribution/uncertainty. No external model is currently integrated.

### Privacy controls and limits

- There is no zero-risk claim: screenshots, OCR, titles, URLs, timing, and cursor behavior can expose sensitive activity even without recording typed characters. On-device processing reduces disclosure to third parties but does not protect files from other local readers or backups by itself.
- Apply exclusions before screenshots, OCR, or detailed input persistence. Recheck foreground context around captures to avoid app-switch races. Protected/password fields, private browsing, denied contexts, and unavailable secure-input state must cause detail capture to stop; detection is imperfect, so provide allowlisted capture mode for a stronger boundary.
- Crop/mask before saving images; redact sensitive OCR locally before persistence. Do not collect clipboard contents or accessibility text-field values by default. Existing regex skip lists alone are not sufficient. Redaction cannot recover exposure once an unmasked frame was written.
- Keep precise raw event data only in a bounded RAM buffer, discard it promptly after aggregation, and persist coarse summaries required by the story. Proposed initial limits: at most 30 seconds of transient event context and at most 24 hours of detailed event summaries; retain longer-lived derived memories only under separate settings. These limits are implemented for the new input collector; longer-lived ordinary capture/memory data keeps its existing policy.
- Store persisted data with restrictive local file permissions; design encryption with an OS-protected key before wider use. No sensitive text/events in debug logs, analytics, crash uploads, or cloud sync. Export must be explicit. Current JSON/JPEG storage remains plaintext. New input/control/provenance files use private permissions; encryption is not implemented.
- Session/time-range deletion must cover event records, screenshots, OCR, linked memories, caches, and validation replay copies. If an aggregated item spans sessions, remove the affected evidence and recompute summaries instead of deleting unrelated work. Existing replay directories also contain personal captures.
- Test the collector schema for absence of raw key/clipboard values, paused/excluded transitions for no detail writes, and event ordering/context attribution for no cross-app leakage. Test revocation and secure-input gaps without weakening macOS protections.

## Commands

Run from the repository root; do not run two trackers concurrently because they share memory and PID files.

```bash
# Start a fresh session with the integrated code
.venv/bin/python lmemm.py

# In another terminal, or after Ctrl-C
.venv/bin/python lmemm.py memory 5 --content
.venv/bin/python lmemm.py peek

# Run the test suite on macOS with graphics-service access
.venv/bin/python -m unittest discover -s tests -v
```

Background alternative: `PY=.venv/bin/python ./run.sh start`; inspect with `./run.sh log`; stop with `./run.sh stop`. Screen Recording permission belongs to the launching app, and browser URL access may prompt for Automation permission.

The approved stable identity, dictation safeguards and first input-timeline increment are implemented. Live identity/dictation/input validation is pending. Next: the scripted input check, then foreground geometry, self-observation and attribution repairs before recall. Keep actual results separate from proposed behavior.

## Implementation review decisions

- Used a feature branch in the existing workspace to preserve the active launch path and prior fixes. Cost: less filesystem isolation than a separate worktree; recovery stash and scoped commits remain available.
- Added the matching ApplicationServices PyObjC binding because Quartz does not expose AX inspection. Cost: one additional dependency; missing native inspection still disables input detail.
- Used an annotated listen-only tap and event target-process metadata to strengthen attribution. Cost: events with absent target metadata are dropped; live coverage requires measurement. No character/keycode APIs are read.
- Block deletion while a retained item still needs a screenshot owned by the requested session. Cost: some deletion requests require resolving shared image ownership first; unrelated source evidence is preserved.
- Committed the coupled input integration with its existing local content/identity/dictation dependencies so a clean checkout is runnable. Cost: a larger integration diff, verified together by the full suite.
- Kept the feature branch locally without merging or pushing; integration was not part of the authorized implementation. Cost: the repository's main branch remains behind the working feature until the user chooses integration.

Independent review found and corrected deleted-content duplication in retained snapshots, inherited pins/first-seen metadata, delayed event attribution, shared screenshot removal, all-session retention and pending deletion recovery. The record cap now reports capacity loss. No review minors remain deferred. Live acceptance remains pending.
