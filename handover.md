# LMemM — continuation handover

Updated 2026-10-10. Start with [current context](docs/current-context.md) and the
[hybrid project-memory MVP spec](docs/specs/2026-10-10-hybrid-project-memory-mvp.md).

## Worktree and current task

Use `.worktrees/semantic-project-memory` on `feat/semantic-project-memory`.
Main is integrated through `42d7f0e` (merge `e94d03a`); crash guard `11f5f3e` follows.
These local updates are not pushed. Root main and its modified context.md are preserved.
The local .env canary stays untracked. Do not create a replacement branch or replay old stashes.

User chose **Overview · Memory** project tabs and the focused hybrid-memory scope.
The written design has passed a fresh builder check but still awaits user approval.
After approval, use Superpowers writing-plans. Do not begin implementation or follow
remaining tasks in the superseded October 7 plans until the new plan exists.

## Scope in one paragraph

Approved VS Code visible excerpts and intentional project notes become retained,
citable evidence. Keyword and local vector search find relevant passages; supported
project/claim/reference links add context. The existing native project page gains a
Memory tab with search, source detail and a grant-specific agent-context preview.
One read-only MCP client can resume the same project using the same backend. Browser
semantic intake, universal understanding, graph visualization and agent writes are deferred.

## Existing behavior and outstanding proof

The normal tracker/UI and experimental semantic pilot exist as separate flows. The
new index, tabs, unified notes, supervised service and MCP are proposed, not implemented.
One live explicit decision/task recall test passed; no general model acceptance exists.
Latest 693 Python tests passed after self-AX guards; 6 Node tests passed during integration.
Native abort: own-process background accessibility reads are guarded, but the original
open-project/app-switch test still needs a live retest. Do not call the shutdown fixed
solely from the unit suite. Resource and multi-project acceptance remain open.

## Commands and records

From this worktree, use `../../.venv/bin/python` as Python:

```bash
PYTHON=../../.venv/bin/python ./scripts/test.sh
node --test extensions/lmemm-source/bridge.test.js
../../.venv/bin/python lmemm.py start
```

Do not run duplicate trackers. The [pilot runbook](docs/live-semantic-pilot.md) is for
the existing separate experiment, not the planned beta startup experience.
[Prior detailed handover](docs/handover-2026-10-08.md) and
[archived context](docs/history/2026-10-10-before-hybrid-scope.md) preserve history.
All evidence/model caches, grants and runtime configuration remain local and ignored.
