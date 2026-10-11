# LMemM — current context

Updated 2026-10-10. This is the active continuation entry point.

## Current decision and next action

The user selected a focused developer MVP: approved VS Code visible content and
intentional project notes; keyword + local vector retrieval over evidence; small
supported graph relationships; read-only MCP for one agent; and **Overview · Memory**
tabs within the existing project window, with source inspection and agent-context preview.
Browser semantic intake and a visual graph explorer are out of this increment.

The [new written spec](specs/2026-10-10-hybrid-project-memory-mvp.md) is drafted and
has passed a fresh independent builder check (no blocking questions). Full written
user approval is still pending. Next: user reviews the spec, then Superpowers
writing-plans creates the implementation plan. Do not implement from the superseded
October 7 plans. Detailed technical defaults in the new spec are proposals for review.

## Branch and preservation

Work in `.worktrees/semantic-project-memory`, branch `feat/semantic-project-memory`.
Latest main included: `42d7f0e`, merged in `e94d03a`. The tested self-accessibility guard
is committed in `11f5f3e`. This documentation revision follows it. Local commits have
not been pushed. Root main remains at its earlier checkpoint with local context.md
edits; do not reset or overwrite them. `.env` is an untracked local canary; never add it.
Backup branches preserve the pre-main-update states. No worktrees were deleted.

## Implemented versus proposed

Existing: normal Mac capture/OCR, note/pill/project/menu/settings UI, event trail,
and separate VS Code semantic pilot with SQLite evidence, source-backed claims,
retention, scoped recall and citations. Native project tree and semantic workspace
IDs are not yet unified. The normal capture flow does not feed the semantic pilot.

Not yet implemented: embedding index, hybrid search, new Memory tab, unified project
note synchronization, supervised memory-service startup, MCP and real agent resume.
One live project previously returned an explicit decision/reason and an open task;
this is not general semantic acceptance. No local extractor passed the overall gate.
Reviewed v2.4 1.5B result: 5 correct / 1 false assertion on a tiny held-out set; later
adapter changes require fresh evaluation. See the [benchmark index](benchmarks/project-memory/README.md).

## Verification and native abort

Latest suite: 693 Python tests passed after the self-accessibility guard; latest
extension run: 6 Node bridge tests passed during main integration. These are historical
results for those revisions, not tests of the proposed hybrid MVP.

User smoke run on October 10 aborted after opening the project window. Unified log
for PID 89486 reported off-main NSMenu mutation, NSRemoteView assertion and
NSInternalInconsistencyException. Background AX readers could inspect LMemM's own
foreground UI. PID-based self guards now prevent that path; four regressions fail
before and pass after. The original live sequence still needs retesting. Memory
warnings are not evidence that memory pressure caused the abort.

Use the user's terminal for real testing; don't start a second tracker. Optional
restart command from the feature worktree:

```bash
umask 077
../../.venv/bin/python -X faulthandler -u lmemm.py start 2>&1 | tee data/smoke-test.log
```

## Documents

- [Active draft spec](specs/2026-10-10-hybrid-project-memory-mvp.md)
- [Short handover](../handover.md)
- [Prior complete context](history/2026-10-10-before-hybrid-scope.md)
- [Existing pilot status](semantic-project-memory-status.md) and [pilot runbook](live-semantic-pilot.md)
- [Architecture](architecture.md), [README](../README.md), [benchmark evidence](benchmarks/project-memory/README.md)

Old specs/plans remain historical records with supersession banners. Their uncompleted
roadmaps are not a competing active scope. No model assets, grants, private evidence,
.env contents or runtime configuration belong in publication.
