# LMemM — current context

Updated 2026-10-11. Active work is now on **local `main`**, explicitly authorized by the user. `origin/main` was fetched at `42d7f0e`, which is included. No push was made. The old feature worktree is retained as a checkpoint, not the active implementation workspace. Root `context.md` is preserved untracked; the named `preserve user context before memory MVP main integration` stash is also retained. Do not stage that file, read/stage the worktree `.env` canary, or replay the stash blindly.

## Implemented MVP

The approved [spec](specs/2026-10-10-hybrid-project-memory-mvp.md) and [plan](plans/2026-10-10-hybrid-project-memory-mvp.md) have been implemented through the backend, service, native integration and MCP tasks:

- Versioned SQLite project bindings, scoped grants, retained evidence chunks and exact citations.
- Keyword + local MiniLM embeddings, incremental bounded vector generations, hybrid ranking and supported one-hop references.
- Explicit note decisions/reasons/tasks, cited context packets, deletion/revocation/quota fences.
- Private app-supervised service with asynchronous native client, pause/quit/lock lifecycle hooks and an owned cloud-disabled model runtime.
- Durable native JSON-note reconciliation for new explicitly project-scoped notes, including edits/done/reopen/delete. Legacy/ambiguous OCR notes are not imported.
- Native Overview / Memory tabs, time filters, Return-only search, project-note entry, retained-source inspection, setup and normal VSIX packaging.
- Official SDK read-only MCP adapter, separate agent disclosure approval, exact grant-specific context preview and explicit copy.

Browser semantic intake, repository crawling, graph visualization, agent writes and model-generated claims are outside this MVP. The local selected embedding model is `all-minilm:22m`, 384 dimensions; weights are installed only after explicit setup.

## Verification and acceptance

Post-review full suite: **807 Python tests passed**, plus **6 Node bridge tests** and seven refreshed real AppKit synthetic states. All ten material independent-review findings, plus provenance presentation, were addressed in one regression/fix pass. See the [review and decisions](benchmarks/project-memory/hybrid-mvp/review-and-decisions.md).

Frozen production held-out retrieval: hybrid Recall@5 20/20; keyword 15/20; paraphrase 10/10 versus keyword 5/10; exact 10/10 both. Fresh deterministic assertion set: 8/8 supported claims across 20 cases, zero unsupported reasons/citations. These are small synthetic measurements.

10k authorized-chunk synthetic hybrid search: warm p95 0.251s, absolute probe RSS 59.9MB, 60-second probe idle sampled. Document vectors were duplicated to isolate index cost; this is not paired native runtime acceptance. Device: Apple M2 Pro, 32GiB RAM, macOS 27.0.

Real AppKit synthetic pane states were displayed and captured by window ID. A real hosted Codex resume test used only two synthetic notes, called the MCP context tool, and cited both exact evidence IDs. No personal project evidence was enrolled or transmitted.

**Still pending:** original open-project/app-switch native shutdown retest, physical sleep/lock acceptance, the paired 30-minute native resource workload (including runtime RSS/energy and live indexing latency), real extension installation/enrollment acceptance, and three consented external testers. Do not call launch complete or claim the original shutdown is fixed solely from tests. See [acceptance](benchmarks/project-memory/hybrid-mvp/acceptance.md).

## Run locally

Use the root checkout now:

```sh
cd /Users/divyaanshseth/Documents/LMemM/LMemM
.venv/bin/python lmemm.py start
```

Do not start a second tracker if the user's terminal is already running one. Open a project → Memory → Enable Memory. Setup, extension connection, agent disclosure and test steps are in the [runbook](hybrid-memory-runbook.md). Automated tests did not enroll personal sources or leave a test service running.

The execution decisions and final findings are preserved in the linked review record; commit history and acceptance records are durable. Superseded October 7 plans remain historical, not competing scope.

## Follow-up: manual test launch repair

The isolated manual session lives under ignored `data/memory-mvp-test-20261011/`.
A setup-again action exposed in-place AppKit relaunch losing macOS registration;
the pill survived but the menu-bar item stayed at `(0, 0)`. Tracker and permission
restarts now spawn a fresh process, and `lmemm.py open` offers direct window access.
The local test launcher now honors CLI arguments and opens the window on startup.
The affected session was saved and relaunched; native app registration and normal
menu-bar placement were observed. Follow-up full suite: 811 tests passed. This
fix does not establish the unrelated original foreground-switch abort acceptance.

## Follow-up: source verification loop

A real manual VS Code connection exposed stale `connect` replay deleting an
already accepted acknowledgement after the challenge tab closed. The service
now ignores replayed connect sequences and verifies stable native identity
rather than requiring the acknowledged tab's old title to remain visible.
Actual native-window changes still invalidate registration. The extension now
publishes immediately after reading its first acknowledgement, avoiding an
extra polling interval before its initial snapshot/heartbeat. Two reproduced
failure tests were RED→GREEN; a native-window-change rejection test also passes.
The extension handshake test now requires a snapshot on the first ack poll.
Full suite: 814 Python tests and 6 Node tests passed. The local extension was
reinstalled, test tracker restarted, and Alpha opened in a fresh VS Code window.
A fresh manual connection is still needed to establish live capture acceptance.

### Pause/resume source connection follow-up (2026-10-11)

Manual capture reached Alpha (`CAPTURE_ALPHA_ONE` retained), but the saved TWO
edit was absent after pause/resume. Pause/resume rebuilt the bridge session,
leaving VS Code on an obsolete token. They now publish the current intake
revision and active state on the existing connection, clearing snapshot dedup;
workspace permission changes still rotate sessions. Regression reproduced
before the fix. Full suite: 814 Python tests and 6 extension tests passed.
Old ONE snapshots remain searchable by design; search TWO to check fresh capture.

The next manual pause test exposed a second failure: the bridge's updated grant
revision was being used as the source content-policy revision, so storage
rejected resumed snapshots. Intake now applies the content-policy revision only
after rechecking the current grant revision, pause state and active binding.
A service regression exercises real handshake, pause/resume, snapshot retention
and accepted acknowledgement. Full suite: 815 Python tests and 6 Node tests pass.

### Portability and readiness remediation (2026-10-13)

Integrated cofounder setup branch through b84f6db into local main, preserving
75d9370's runtime failure fixes. Resolved stale-PID process killing, unsupported
Insiders discovery (including symlink aliases), unconditional VS Code quit on
Connect, inconsistent startup deadlines and global connection status. Added
owned-child cleanup after startup failure and safe keyword/capture resume when
semantic runtime is unavailable. Private service logging refuses symlink and
hard-link targets before truncation. Setup guide/handover match the new Settings
UI and explicit one-time editor reload. No new push yet.

Fresh requirements-only Python environment: 839 tests pass; six Node tests pass.
Ten real native synthetic states rendered and captured. Held-out real local-model
hybrid retrieval remains 20/20 Recall@5. Independent review identified the fixed
editor-symlink edge case. See the portability audit for evidence and limits;
second-Mac setup, physical crash acceptance, paired resources and external users
remain pending.
