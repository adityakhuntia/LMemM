# LMemM — current context

Updated 2026-10-07, America/New_York. Historical context and handover are in
`docs/history/`. This file records current decisions and verification limits.

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
  `feat/input-timeline` at **0f3b862**. Current checkout is main. Feature/refactor
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
- Widget projects are derived labels. No knowledge graph, semantic inference,
  MCP service or agent retrieval boundary exists yet.

## MVP decision and next work

The user selected **resume work on a project** as the first agent workflow.
The agreed MVP is accurate project knowledge exposed to AI agents through MCP,
with acceptable measured performance and low resource use. Broader companion
features come after this. Graph understanding is now in **brainstorming**;
see [discussion brief](knowledge-graph-discussion.md).

Recommended order: define one agent workflow and evidence quality criteria;
enforce app/site access and foreground source boundaries; establish performance
baseline; build explicit project/artifact associations and source-backed facts;
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
PYTHON=.venv/bin/python ./scripts/test.sh -v
```

One tracker at a time; restart after code/permission changes. README is the user
guide and docs/architecture.md describes the integrated modules.
