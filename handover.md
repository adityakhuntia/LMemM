# LMemM — continuation handover

Updated 2026-10-20. Read [current context](docs/current-context.md), [runbook](docs/hybrid-memory-runbook.md), and [acceptance](docs/benchmarks/project-memory/hybrid-mvp/acceptance.md).

October 20 recheck: fetched all origin refs; remote main is still `9b8efb3`,
already included by local integration `e425854`. No new code to pull or review.
Fresh verification: 878 Python tests, six Node tests and all 13 native synthetic
UI states pass. Existing alias-app command startup correctly reports no running
tracker. No new hosted request was needed for unchanged code; the October 16
synthetic hosted evidence remains the last live AskCodex check. Local fixes
remain unpushed; shared main does not yet contain the local integration.

Latest: remote main `9b8efb3` is integrated with the previously unpushed local
readiness work. See [review and direction](docs/2026-10-16-main-review-and-direction.md).
The new blue UI, grouped sources, sheet flows, focus diagnostics, alias app and
AskCodex are included. Review fixed cross-project/stale answers, MCP registration
overwrite/races, and alias-app child environment/restart handling. Live synthetic
AskCodex passed with one context call and both expected exact citation IDs.
No personal memories were used and global Codex settings were not changed by testing.
Final integrated verification: 878 Python tests, six Node tests, 13 real native
synthetic UI states, successful alias app build and command startup.
The new merge remains local until explicitly pushed; old publication statements
below are historical. Preserve untracked context.md.

User direction: serve developers AND knowledge workers through one outcome,
resuming a project across code/docs/browser work. The documented next-step
proposal is a common resume front door, notes/context without mandatory coding
setup, then one controlled browser/document source. Broader app tracking exists,
but current scoped semantic evidence is still VS Code + intentional notes.
Do not represent the proposed broader sources/brief as already implemented.

App test: `./build_app.sh` succeeds; `open dist/LMemM.app` runs a checkout-linked
alias app. It requires this repo and .venv to stay in place. It is not yet a
portable distribution. Fresh app permissions must be granted to LMemM itself.
For synthetic UI testing use `scripts/memory_ui_smoke.py --output <directory>`;
this avoids starting personal capture or invoking hosted AI.

2026-10-13 readiness follow-up: cofounder setup improvements through `b84f6db`
are integrated into local main, preserving the audit fixes. All five concerns
from the [systematic audit](docs/2026-10-13-memory-portability-audit.md) have code
resolutions: no stale-PID killing; standard VS Code only (including symlink
checks); Connect keeps editor windows open; one 45-second startup budget;
project-scoped connection status. Failed model startup is cleaned up, semantic
requests fail closed, and capture/keyword recall can still resume. Service logs
reject symlinks/hard links and use private permissions. The setup/error UI,
Ollama layout compatibility and visible installation progress are included.

Validation: **839 Python tests in a fresh pip-only virtual environment**, six
Node tests, ten real native synthetic UI states, and refreshed real local-model
held-out retrieval (20/20 Recall@5). Independent review's editor-symlink finding
was reproduced and fixed. This new integration is local and not yet pushed;
the October 11 push remains `66bcd65`. A clean second Mac, original crash run,
formal paired resource workload and external testers remain launch gates.

For users: choose the project → Memory → Settings, install the extension and
local model, then Connect. Reload the VS Code window once after extension
installation if it was already running; LMemM never quits the whole editor.
Use standard VS Code, not Insiders. Follow the updated runbook for exact setup
and failure recovery. The October 11 walkthrough below is historical; its
source-sharing controls now live in Settings.

Work in the root checkout on **main**, per the user's explicit request. Remote main was fetched and verified as an ancestor before this delivery. Publication is authorized. Preserve untracked user `context.md` and its integration safety stash. The old feature worktree remains a checkpoint with local assets; never stage its environment files or force-clean it.

The hybrid MVP backend, private supervised service, durable native-note sync, native Overview/Memory UI and official SDK MCP adapter are implemented. Latest verification: **815 Python tests and 6 Node tests pass**. Synthetic native screenshots, held-out retrieval (20/20 Recall@5), fresh assertion precision (8/8 supported), 10k full-search probe (0.251s p95), and an actual synthetic-only hosted Codex resume are recorded. These synthetic benchmarks are not guarantees for arbitrary personal data.

The whole-implementation review and regression fixes are complete; see [review and decisions](docs/benchmarks/project-memory/hybrid-mvp/review-and-decisions.md). The user confirmed live capture, pause/resume without reconnecting, project notes, semantic search, restart persistence, sleep/lock recovery and Alpha/Beta isolation. A supplied screenshot confirms Beta's retained citation text, timestamp and workspace path. Stability is good so far. Original crash-sequence acceptance, measured paired 30-minute resources and three external testers remain pending; this is a successful local smoke test, not launch approval.

Start from the root with `.venv/bin/python lmemm.py start`, only when no other tracker is running. Follow the runbook to enable a project explicitly; no personal sources were enrolled by implementation tests.

## Features and their value

| Built feature | Value for the user | Boundary |
|---|---|---|
| Overview / Memory project tabs | Find retained context alongside current project work | No visual graph explorer |
| Explicit workspace enrollment and isolation | Keep one project's evidence out of another project's answers | Approved roots and source permissions required |
| Visible VS Code capture | Remember permitted text actually viewed, with file identity | Not a repository-wide crawler |
| Local vectors plus keyword search | Find paraphrases as well as exact names or markers | Searches retained evidence; semantic mode needs the local model |
| Supported decisions, tasks and relationships | Recover explicit decisions and next steps with evidence | Conservative extraction; experimental generated claims disabled |
| Project notes and durable synchronization | Save important context intentionally; reconcile note/task changes | Add new notes through Memory → Project notes |
| Retained citations | Verify exact historical text, timestamp and source location | Historical snapshots can differ from today's file |
| Pause/resume and sleep/lock barriers | Control collection and recover safely | Reconnect source sharing after an app restart |
| Supervised private service, indexing and retention | Persist searchable local context across sessions | Formal sustained resource acceptance pending |
| Scoped MCP and context preview | Give an approved agent relevant project context with citations | Explicit access/disclosure; preview alone sends nothing |

The knowledge graph is a hybrid evidence system: vectors retrieve related
content; structured project, source, task and decision relationships organize
supported context. Its practical benefit is resuming work with verifiable
context, rather than reconstructing it from scattered files and notes.

## Start the prepared local demo

From this repository root, with the test tracker stopped:

```sh
open -a Terminal "$PWD/data/memory-mvp-test-20261011/start.command"
```

If already running but the window is closed:

```sh
.venv/bin/python data/memory-mvp-test-20261011/launch.py open
```

This ignored dataset exists on this machine only: Alpha/Beta workspaces, model
assets and a separate session. Do not rerun its setup script or run two trackers.
Other checkouts should use normal startup above and the runbook for setup.

## Live demonstration and test walkthrough

1. Open **Memory Test Alpha → Memory**. Search `Which database did we choose?`
   and press Return. Expect Alpha's SQLite evidence, never Beta's PostgreSQL.
2. Inspect a retained citation. Check exact text, timestamp and project path.
   Close source to return. Clear search with Cmd+A then Delete inside the field.
3. In **Memory → Project notes**, add `TODO: Verify payment retry handling before release.`
   Wait for indexing, then search `What payment failure work is left?`. Expect
   the new note with its citation.
4. Use **Reconnect source sharing**, copy its grant path, and in the Alpha
   VS Code window run **LMemM: Connect Project Memory** from Cmd+Shift+P.
   Paste the path and leave native verification visible until its tab closes.
5. Open `workspace-alpha/capture-test.md`. Save a fresh marker such as
   `DEMO_CAPTURE_FIVE`, keep it visible five seconds, then search it in Alpha.
   Expect a retained observed-content snapshot.
6. Pause Memory. Change FIVE to `DEMO_CAPTURE_SIX`, save and keep visible.
   Search SIX: absent. Resume, return to the editor for five seconds, search
   SIX again: present **without reconnecting**. FIVE remains historical evidence.
7. In **Memory Test Beta → Memory**, search SIX: no result. Inspect the invoice
   note's citation to see its separate Beta source path.
8. Quit from the menu bar, restart, and search existing notes: still present.
   Reconnect VS Code after restart. Lock/unlock or sleep/wake pauses capture;
   explicitly resume after returning.
9. Additional manual checks still to confirm on the final build: mark the TODO
   done/reopen/delete and verify open tasks/search follow; disconnect/re-enable
   project Memory; inspect context preview; try a separately approved real agent
   connection. Automated coverage does not substitute for those manual checks.

Logs: `data/memory-mvp-test-20261011/tracker.log`. Report the failing step,
expected/actual result and final log lines if a regression occurs.

## Short demo video script (about 90 seconds)

No video was recorded: desktop control failed to initialize its native pipe.
For a live recording on this Mac, press **Shift+Cmd+5 → Record Selected Portion**,
frame the app and synthetic Alpha editor, and stop via the menu-bar recording button.

| Time | Show | Explain |
|---|---|---|
| 0–15s | Alpha Memory tab | “This project remembers decisions and unfinished work.” |
| 15–35s | Paraphrase search, then citation | “Find a decision without its exact wording, and verify its source.” |
| 35–50s | Add and retrieve payment TODO | “Save context deliberately for the next session.” |
| 50–75s | Connected editor: pause, change fresh marker, resume, search | “Capture respects pause and resumes from approved visible work.” |
| 75–90s | Beta returns no Alpha marker | “Projects keep separate memories.” |

Use fresh markers and wait for actual capture/indexing; extend the recording
if necessary. Record the synthetic workspace only and exclude personal notifications.

## Future plans and remaining launch gates

1. Formal original crash-sequence test and paired 30-minute baseline/runtime
   measurements of CPU, RSS and energy with a sustained retained workload.
2. Three consented external testers and the remaining manual lifecycle/agent
   checks listed above. No testers have been contacted as part of this delivery.
3. Clearer connection/status wording, simpler recovery and packaged onboarding.
   These are planned improvements, not claimed delivered features.
4. Broader real-work retrieval evaluation; later connectors and richer supported
   relationships driven by observed need. Visual graph exploration stays outside
   this MVP's scope.

Latest code fix before this handover: `f229add` (resumed snapshot storage).
Live testing also fixed native relaunch/menu access, handshake replay and pause
session rotation. See the [spec](docs/specs/2026-10-10-hybrid-project-memory-mvp.md)
and [plan](docs/plans/2026-10-10-hybrid-project-memory-mvp.md) for implementation detail.
