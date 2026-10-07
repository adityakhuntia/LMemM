# LMemM — current context

Updated 2026-10-07, America/New_York. Historical context and handover are in
`docs/history/`. This file records current decisions and verification limits.

## Document map

- [README](README.md): normal tracker setup and user commands.
- [Architecture](ARCHITECTURE.md): capture modules and experimental semantic boundary.
- [Semantic handover](docs/semantic-project-memory-status.md): implemented interfaces,
  test instructions and remaining source/MCP prerequisites.
- [Benchmark index and reviewed results](docs/benchmarks/project-memory/README.md):
  measured claims, privacy probes, model failures and reproduction.
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
- Widget projects are derived labels. The fixture-only semantic core exists on this feature branch; it is not connected
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
exist there; no model has passed acceptance. Live source adapters and MCP remain
separate increments. See [implementation status](docs/semantic-project-memory-status.md).

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

Verification: **163 tests pass, including 53 semantic tests**. Three local models were
evaluated with the frozen extractor. Reviewed heldout assertion precision/recall:
Qwen2.5 0.5B 67%/40%, Qwen2.5 1.5B 83%/100%, Qwen3 1.7B 71%/100%. Each run has
32 extraction timings and zero leaks across 13 controlled privacy probes. Five gold
claims and short synthetic inputs are a narrow benchmark, not general accuracy.
No model passes the precision gate; resource/selection acceptance remain false.
No local model is enabled in normal capture; no feature merge or push was performed.

Next order:
1. Improve precision and browser association using broader development examples and
   a fresh heldout split; do not tune on the inspected v2 heldout. Keep confidence
   status separate from source truth. See the benchmark index for actual errors.
2. Complete FTS candidate selection, independent-episode corroboration, all-writer
   quota enforcement, retention scheduling and worker cancellation/state lifecycle.
3. Add authoritative permission-checked live VS Code/browser source envelopes and
   foreground isolation, without enabling inference before quality/resource gates pass.
4. Benchmark representative enabled-worker sessions and power, then expose scoped
   read-only MCP retrieval for an agent resuming a project. Hosted inference remains
   a separate future privacy discussion.
