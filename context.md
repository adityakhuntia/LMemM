# LMemM — current context

Updated 2026-10-08, America/New_York. Historical context and handover are in
`docs/history/`. This file records current decisions and verification limits.

## Current handoff snapshot — 2026-10-08

- Worktree/branch: `.worktrees/semantic-project-memory`, `feat/semantic-project-memory`.
- Integrated all four new Aditya main commits through `e5cd6ed`: lighter capture,
  cost-control docs, rule-based context export, consolidated memory and CLI menu.
- Normal tracker and semantic VS Code pilot remain separate flows. `lmemm.py` now
  opens the menu; `lmemm.py start` starts capture. Normal storage uses schema-3
  `memory.json` with readable things and internal items, not `.index.json`/`pending.json`.
- Live one-project semantic test passes capture, exclusion canary, saved notes,
  bounded recovery, a supported SQLite decision/reason, an open restart-test task
  and exact source citations in recall. This is a small case, not general model acceptance.
- Current regression verification after merge: 251 Python / 92 semantic / 6 Node tests pass.
- Open: general semantic quality, browser/site permissions, representative resources,
  broader lifecycle and multiple-project native acceptance, scoped MCP/agent handoff.
- Main checkout was not changed by this feature merge. This feature publication includes
  all semantic work and current main integration; records below are historical checkpoints.
- [Current handover](docs/handover-2026-10-08.md) is the primary continuation guide.

## Document map

- [README](README.md): normal tracker setup and user commands.
- [Architecture](ARCHITECTURE.md): capture modules and experimental semantic boundary.
- [Semantic handover](docs/semantic-project-memory-status.md): implemented interfaces,
  test instructions and remaining source/MCP prerequisites.
- [Benchmark index and reviewed results](docs/benchmarks/project-memory/README.md):
  measured claims, privacy probes, model failures and reproduction.
- [Live semantic pilot design](docs/specs/2026-10-07-live-semantic-pilot-design.md):
  VS Code source bridge, foreground checks and opt-in experimental testing across
  approved projects; implemented, one-project native acceptance demonstrated.
- [Live pilot runbook](docs/live-semantic-pilot.md): exact start/connect/control/test commands.
- [Live pilot implementation plan](docs/plans/2026-10-07-live-semantic-pilot.md): task/review status.
- [Approved semantic design](docs/specs/2026-10-07-automatic-project-memory-design.md)
  and [implementation plan/status](docs/plans/2026-10-07-automatic-project-memory.md).
- [Product/knowledge-graph discussion](docs/knowledge-graph-discussion.md): MVP intent.
- [Historical handovers](docs/history/): earlier capture/input/dictation work.

Current worktree: `.worktrees/semantic-project-memory`, branch
`feat/semantic-project-memory`. The root main checkout has not been merged or changed
by this semantic increment. Treat the benchmark index as the source of current model
results; v1 type scores and v2 assertion scores are different measurements.

## Integration and closed work

- Aditya's `refactor/cohesive-core` through `42c38b7` includes every published
  `feat/input-timeline` commit through `7ccec46`. Integrated locally in `627f0e4`.
- Our foreground-evidence spec/plan were preserved under `docs/specs/` and
  `docs/plans/`, matching the refactor's document layout. No foreground-window
  product implementation has started; the plan must be adapted to `macos.py`,
  `config.py`, `store.py` and the agreed AI-agent MVP before execution.
- Refactor module extraction, pending-note controls/reminders and Left/Plan
  widget integration: **closed at the verification level below**.
- Repaired pending-note deletion: manifest recovery rebuilds `pending.json`
  using private atomic writes; deleted quotes disappear while retained notes stay.
- Repaired note-state provenance: unvisited items changed by controls are included
  in contributions; an explicit empty completion map preserves reopen operations.
- Repaired same-second offline command collisions using nanosecond evidence IDs.
- Existing keyboard/cursor summaries, content excerpts, identity repair,
  dictation safeguards, retention and provenance work remain integrated.
- Validated integration and repairs published to GitHub `main` and
  `feat/input-timeline` at **0f3b862**. That integration was on main. Feature/refactor
  branches are preserved; branch cleanup is not performed.

## Verification

- Full native regression suite: **110 tests passed**, 2026-10-07. Whitespace and
  syntax checks passed; new regression tests failed before their fixes.
- Independent review identified three note-provenance defects; fixes were
  reviewed again with no remaining blockers in the reviewed integration.
- Native smoke: generated foreground window, periodic display capture, actual
  Vision OCR, memory persistence, saved note, widget rendering and marking done
  passed. Only temporary data was used, removed on exit. No live input listener
  or microphone was started.
- Initial note-trigger capture was rejected by context validation; this is not
  a hotkey/note-capture acceptance pass. Earlier widget-only native checks passed.

## Open QA and current limitations

- Real Google Meet behavior, sustained CPU/RAM/power benchmarks, longer sessions
  and multiple displays remain unverified. No claim of optimized performance.
- Latest Ctrl+Tab/Cmd+Tab live repeat, full pause/lock/exclusion lifecycle,
  real two-session Google Docs and real speech/hotkey acceptance remain open.
- Screenshots still cover displays; selecting the first eligible CG window can
  yield wrong foreground bounds. Surrounding UI and self-observation remain
  known evidence-quality problems. Native smoke does not resolve them.
- App/site exclusions are heuristic defaults, not user-configurable access
  policies. Input alone is explicitly opted in and restricted to VS Code.
- Storage is local plaintext. OCR/activity/decision quotes do not establish
  authorship, intent, verified decisions or completed work.
- Widget projects are derived labels. The semantic core and separate opt-in VS Code pilot exist on this feature branch; normal capture is not connected
  to capture. No live knowledge graph, MCP service or agent connection is enabled.

## MVP decision and next work

The user selected **resume work on a project** as the first agent workflow.
Automatic semantic understanding/linking is required; manual attachment is not
the default workflow. First infer project anchors from workspace folders and
document context, then associate activity automatically. Arbitrary project
discovery comes later; corrections remain optional. Current MVP inference is
strictly on-device; hosted inference remains a future privacy discussion and
must not be an automatic fallback. Semantic budgets are approved at 250 MiB retained evidence and 3 GiB runtime;
measured enabled-worker resource acceptance remains open.
The agreed MVP is accurate project knowledge exposed to AI agents through MCP,
with acceptable measured performance and low resource use. Broader companion
features come after this. Initial source scope is VS Code plus permitted browser
sites. A [proposed written spec](docs/specs/2026-10-07-automatic-project-memory-design.md)
is approved; the [discussion brief](docs/knowledge-graph-discussion.md)
records the selected direction. The [semantic-core implementation plan](docs/plans/2026-10-07-automatic-project-memory.md)
was approved and executed in `.worktrees/semantic-project-memory` on
`feat/semantic-project-memory`. The fixture-driven core and local evaluation
exist there; no model has passed acceptance. The separate VS Code pilot is implemented below; browser adapters and MCP remain
future increments. See [implementation status](docs/semantic-project-memory-status.md).

Recommended order: define one agent workflow and evidence quality criteria;
enforce app/site access and foreground source boundaries; establish performance
baseline; build automatic anchored project/artifact associations and source-backed facts;
expose scoped read-only MCP retrieval; evaluate inferred relationships before
allowing them to affect agent answers. Tab-switch patterns are weak evidence,
not proof of a shared project.

## Useful commands

```bash
.venv/bin/python lmemm.py --input-events --input-app com.microsoft.VSCode
.venv/bin/python lmemm.py notes
.venv/bin/python lmemm.py notes done NOTE_ID
.venv/bin/python lmemm.py notes reopen NOTE_ID
.venv/bin/python lmemm.py memory 100 --events --content
.venv/bin/python -m unittest discover -s tests -v
```

One tracker at a time; restart after code/permission changes. README is the user
guide and ARCHITECTURE.md describes the integrated modules.

## Semantic increment — 2026-10-07

Implemented in the isolated feature worktree: permission-checked SQLite evidence,
canonical workspace/artifact identity, bounded episodes, validated extraction jobs,
source-backed claims and relationships, explicit task transitions/corrections,
retention/deletion, scoped project context and citations. Existing CLI capture does
not feed semantic evidence yet. Session deletion cleans the semantic DB when present.

Closed in the continuation: exact assertion/reason/state/citation scoring; source-index
quote selection; boundary-safe explicit project references; mixed public/private
revocation audits; independent review and regression repairs. Model output chooses
a quote/category; it cannot fabricate quote text or arbitrary IDs. Reasons are currently
limited to bounded explicit “because” excerpts. Complex multi-claim passages remain a gap.

Verification: **191 Python tests pass, including 81 semantic tests; 6 Node tests pass**. Three local models were
evaluated with the frozen extractor. Reviewed heldout assertion precision/recall:
Qwen2.5 0.5B 67%/40%, Qwen2.5 1.5B 83%/100%, Qwen3 1.7B 71%/100%. Each run has
32 extraction timings and zero leaks across 13 controlled privacy probes. Five gold
claims and short synthetic inputs are a narrow benchmark, not general accuracy.
No model passes the precision gate; resource/selection acceptance remain false.
No local model is enabled in normal capture; no feature merge or push was performed.

Next order:
1. Run the [live pilot checklist](docs/live-semantic-pilot.md) across two approved projects. Confirm native handshake, real visible text, exclusions, switching, pause/restart/deletion and recall usefulness. No user content has been captured for this validation.
2. Record live results, handover and push the feature branch after confirmation. Do not merge main.
3. Improve automatic semantic understanding using observed pilot errors and broader development/fresh heldout examples. Complete FTS candidate selection and independent-episode relationship corroboration.
4. Measure representative enabled-worker RAM/CPU/power, improve precision and build browser source adapters with explicit website permissions.
5. Expose scoped read-only MCP retrieval for an agent resuming a project after quality/privacy/resource acceptance. Hosted inference remains an open privacy discussion.

## Live semantic pilot — engineering closed, live acceptance open

The revised direction supports multiple approved VS Code projects/windows and visible tentative recall. Precision gates govern default agent use, not explicit experimental testing.

Built and tested: visible-range VS Code extension; private token/session/revision bridge; random native-title registration challenge; secure-focus/root/symlink/exclusion gates; metadata heartbeats and accepted-source dedup; lifecycle cancellation barriers; async worker; scheduled 30-day retention and all-writer SQLite page cap; read-only recent project recall with original source quotes/file locators/omission coverage; controls and stopped-session deletion.

Independent review found registration, symlink exclusion, focus/pause cancellation, generation, resumed-publication, disconnect, recent-recall and CLI-directory issues. Regression cases reproduced failures and now pass. Extension-host pause/resume is covered with a mocked VS Code API; this is not a real host acceptance claim.

Metadata-only native smoke: Accessibility trusted; foreground was not verified as approved VS Code, so intake stayed closed. No screenshots/input listener/microphone or user-content inference was started. Model benchmarks remain unchanged and below precision acceptance.

Rulings: one-second publisher poll stays inside the two-second freshness window; resume may require retry while a cancelled request finishes; the 250MiB total reserves journal/reclaim space, leaving roughly one-third for the database; noncanonical/symlink document aliases are rejected; the native title challenge requires a temporary registration tab. These favor inspectable behavior and privacy and may require explicit reconnect/canonical paths.

Pointers: [design](docs/specs/2026-10-07-live-semantic-pilot-design.md), [implementation plan](docs/plans/2026-10-07-live-semantic-pilot.md), [runbook](docs/live-semantic-pilot.md), [semantic handover](docs/semantic-project-memory-status.md). No push or main merge has been performed.

Live QA follow-up: extension loaded and challenge tab appeared, but registration stayed blocked. Native diagnosis showed system AXFocusedUIElement error -25204 while app-scoped focus succeeded. Added app-scoped fallback for unavailable/unsupported system queries, preserving owner/role/secure-field checks. Regression reproduced RED then passed; collector restart and live acceptance remain pending.

Live QA diagnostic: native challenge/focus/geometry checks passed for 27 recorded foreground samples. Found collector focus-boundary revisions were not published to grant.json, leaving extension events permanently stale. Added revision publication on invalidation and regression coverage (RED→GREEN). Collector restart required to load fix; accepted-source live QA still pending.

Live capture check: handshake closed successfully, but accepted source/project counts remained zero. Bridge acknowledgement was absent while publisher retained the old window binding. Added authenticated metadata liveness even when native intake is denied, a two-second crash lease, explicit disconnect cancellation and fresh native challenge recovery when ack is absent. Denied events consume sequence numbers; retries require a fresh sequence. Regression tests reproduced failures, then passed. Actual accepted-content QA remains pending after collector/extension reload.

Live QA checkpoint (2026-10-07): after native-focus/grant/lease repairs, real source intake and read-only recall passed for one approved worktree. Current session accepted 21 trusted-artifact snapshots across README.md (13), input_events.py (4), memory_content.py (4), with 32,568 retained UTF8 text bytes. Recall resolves nine recent original source quotes with timestamps/file locators/citation IDs and reports 12 omitted excerpts/truncation. Six episodes remain unprocessed, expected in evidence-only mode. Current foreground-denied status after returning to Codex is expected; collector stays running and connection ack remains present. This validates native handshake + visible-source capture/storage/retrieval, not semantic-model accuracy or the full acceptance checklist. Still pending: unchanged-heartbeat live repeat, second project, exclusions, pause/lock/restart/deletion, model usefulness and performance.

Unchanged-screen live follow-up: sources rose from 21 to 24 only during three consecutive README view snapshots at 23:09:54–23:09:56 UTC (different retained text hashes); no continuous heartbeat evidence growth followed. Returning to a file can produce a new visit snapshot; initial visible-range changes also produce distinct evidence. Stable-view dedup appears to work for this short check; long-session behavior remains pending.

Extension-pause follow-up: accepted sources are 25 (one above the previous 24); latest source at 23:12:04.828 UTC, with no new snapshots for 47.8 seconds at inspection. Current bridge event is metadata-only heartbeat, focused=false, no spans. This is consistent with the short pause test, but exact pause timing is not retained, so the single extra snapshot cannot be definitively assigned before/after pause. Collector paused=false reflects independent extension pause rather than process-wide pause. Resume check remains pending.

Resume live follow-up: reconnect/re-verification succeeded and accepted sources increased 25→47, with fresh README.md snapshots through 23:14:00.880 UTC. Live resumed intake is confirmed for this approved project. Model mode remains evidence-only; semantic usefulness, exclusion/second-project/deletion tests and performance remain open.

Saved-canary exclusion live check: .env on disk contained exact LMEMM_EXCLUSION_TEST_ONLY marker after save; zero matches in retained blobs/FTS/claim statements/reasons and zero .env artifact records. Exclusion passed for this file/root; broader app/browser/privacy cases remain unverified.

Experimental-model live checkpoint: model-enabled run accepted five additional snapshots (48→53) and completed one extraction job on its first attempt. One grounded observation quote from README was persisted and resolves to retained evidence. No user_note sources, decisions or open tasks were retained. This confirms the local model→validated claim→recall plumbing, not meaningful project-handoff understanding. The intended combined decision/TODO note is absent, so note delivery/task extraction QA remains open. The observation is document content, not proof the user performed the described work in this session.

Intentional-note delivery repair: user confirmed submitting the missing TODO. Regression reproduced a stale revision after the input dialog and a pending note being overwritten before acknowledgement. Notes now refresh the grant after submission, retain a stable identity/timestamp across bounded retries, wait for collector acknowledgement and show a saved confirmation. Pause, focus/source changes, timeout and unavailable bridge discard pending text with a visible failure. Six Node extension tests, 86 semantic Python tests and the full 196-test Python suite pass (native suite required execution outside the sandbox after the sandboxed run aborted). Live delivery and decision/task extraction remain pending after collector restart and extension reload.

Note-command UX follow-up: disconnected, paused or unavailable/excluded active-editor states previously returned silently. These now explain how to connect or open an approved local file. Regression reproduced the silent return; all six Node tests pass. Collector was running, unpaused, in experimental model mode at inspection; live note acceptance remains pending.

Live intentional-note acceptance: two user_note sources are retained exactly: “We chose SQLite because memory should stay local.” and “TODO: Test Restart Recovery”. Their episodes closed on native_focus_boundary without any inference job. Fixed bounded recovery of unprocessed episodes lacking jobs when native focus is verified; prioritize notes, restrict all evidence to currently approved workspace roots and VS Code, preserve cancelled/error jobs without automatic retry. Recovery also covers restart and queue overflow without resubmission. Two regression tests pass; 88 semantic tests and full 198 Python tests pass. Collector restarted with experimental model and retained data; live decision/task extraction remains pending while foreground focus is denied.

Live retest after clean restart (2026-10-07 evening): new session retained both intentional notes, increasing sources to 66. New note evidence is exact SQLite/local decision text and TODO restart text (with a trailing backslash typed in the task). Both note episodes have cancelled inference jobs after two attempts; zero decision/task claims or supporting citations exist. Total jobs: processed 3, cancelled 18. Capture/storage passes; semantic note extraction does not pass. The two-minute foreground wait did not resolve the issue. Focus invalidation and inference cancellation remain too tightly coupled for reliable user workflow; investigate cancellation timing/runtime outcomes and design explicit scoped retry of retained evidence, preserving pause/revocation barriers. Do not ask for repeated note resubmission as the fix.

Cancellation trace (2026-10-07): read-only replay of the latest two retained note episodes against the same cloud-disabled local runtime returned in 2.01s (TODO episode) and 0.85s (SQLite episode). SQLite was correctly selected as decision with exact reason “memory should stay local.”; TODO was selected as suggestion, so task classification remains a separate model quality failure. No replay claims were committed. Native metadata trace: 86 samples AXTextField with unsupported AXSubrole (-25212), secure_input=false, verified=false; after user focused README, 34 samples AXTextArea, same stable window geometry, verified=true. This confirms current secure-field gate denies unknown textfield subroles and editor verification works. Episode/revision records show notes closed within one second on native_focus_boundary; those jobs end cancelled. The prior orphan recovery deliberately excludes jobs already cancelled, so focus recovery cannot revive them. Do not relax secure-field intake. Recommended next increment: separate transient capture-focus cancellation from durable retained-evidence authorization, with bounded explicitly scoped recovery/retry for focus-cancelled work while preserving pause, secure-input, permission, exclusion, deletion and stop barriers; add clear job failure/cancellation diagnostics. Address TODO misclassification with benchmarked source-aware extraction rather than assuming it was only a scheduling issue.

Focus-recovery + task-classification increment: native-focus cancellations receive at most two persisted requeues per episode under existing queue limits, after renewed verified focus and approved-root checks. Late worker completion preserves cancellation reasons, so pause/access jobs do not become automatic focus retries. Explicit retry_notes lets the user recover previously cancelled intentional notes; the request waits for verified focus and pause clears it. Short single-line intentional TODO notes become exact-source tasks even if omitted/mislabelled by the model; document TODOs are not promoted. Runtime adapter version is now v2.5; prior v2.4 benchmark precision does not establish v2.5 accuracy. 92 semantic tests and the full 202-test Python suite pass; retained-note live confirmation follows. No new note submission is required.

Live confirmation 2026-10-08: retained-note recovery succeeded without resubmission. Supported decision: “We chose SQLite because memory should stay local.” with exact reason “memory should stay local.” Supported open task: “TODO: Test Restart Recovery”. Both supporting citations resolve to exact retained user_note quotes; project recall exposes both. Sources 78; jobs processed 12/cancelled 10. The original two note episodes processed on one attempt after one recovery each. The later duplicate-note episodes exhausted their two focus retries and remain visibly cancelled; bounded recovery does not guarantee completion under repeated interruptions. This repair increment passes the tested capture→storage→recovery→source-backed decision/task→recall path. General semantic precision, representative resource performance, broader lifecycle/multi-project acceptance and MCP remain open. Full Python suite: 202 passing tests.
