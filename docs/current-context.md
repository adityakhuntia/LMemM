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
