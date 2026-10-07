# Live Semantic Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans; preserve the user's existing inline execution choice. Use test-first changes and one independent final review.

**Goal:** A usable opt-in live VS Code project-memory loop across approved projects, with inspectable tentative recall and original citations.

**Architecture:** A dependency-free VS Code extension publishes bounded local-file visible excerpts into a private session bridge. Python binds focused clients to native windows, validates workspace permissions, feeds the existing SQLite/episode/worker pipeline and exposes start/control/context commands. Normal capture remains independent; no accepted-model or MCP claim.

**Tech Stack:** Python/SQLite, Node built-in tests, VS Code extension API, read-only macOS AX/CG focus inspection, existing local Ollama adapter.

**Spec:** [Revised live pilot](../specs/2026-10-07-live-semantic-pilot-design.md).

## Global Constraints

- Multiple explicitly approved local workspace roots, at most eight connected clients; one verified focused client at a time.
- Local private bridge only:0700 directories/0600 files, session token, increasing sequences,2second freshness,32KiB ingress,4KiB spans/16KiB envelope.
- Trusted local file buffers/visible ranges only; no screenshots/background/full-file/terminal/chat/keyboard capture. Deny remote, untrusted, excluded, untitled, symlink escapes and unknown focus.
- Separate pilot DB,30day/250MiB storage limit including transient bridge/journaling reserve; cached weights excluded. One inference worker,8episodes/128KiB queue,30second attempt/one retry.
- Experimental model requires explicit flags/configuration; no hosted fallback or automatic runtime/service/model start. Tentative interpretations are inspectable; no confident agent/MCP access.
- Do not wait for passing precision to exercise an explicit pilot. Preserve failed benchmarks and later95%precision/80%recall/resource acceptance gates.
- User initiates real live test. Record actual results, then handover/push feature branch only after confirmation.

## Review Focus

1. A stale client claiming focus must not supply text for a different native window.
2. An approved parent root must not authorize symlink escapes, excluded files or undeclared child workspace identities.
3. Revocation/pause during inference must block stale result commits without stalling capture.
4. Multiple unchanged heartbeats must not grow evidence indefinitely or generate repeated jobs.
5. Context inspection must distinguish observed quotes from completed changes, tentative tasks and verified decisions.

### Task 1: Source protocol and native focus

**Files:** `semantic_memory/live_bridge.py`, `semantic_memory/live_focus.py`, `tests/test_semantic_live_bridge.py`.
**Interfaces:** `Bridge(directory,roots,clock).accept(message,focus)->SourceEnvelope|None`; `Bridge.open_session()` returns private grant; `focused_context()` returns verified bundle/PID/window/bounds or deny reason. Registered client/window binding persists only this run.
- [ ] Write tests for two approved project identities, stale/replayed sequences, wrong token/window, simultaneous focused clients, excluded/symlink/remote/unknown paths and private bounded file reads. Run missing-module RED.
- [ ] Implement strict file protocol and explicit connect-before-snapshot binding; metadata-only heartbeats, deterministic source IDs and active-source tracking.
- [ ] Implement unique AX-focused-window-to-CG matching, secure/unknown rejection and before/after context equality. Unit-test geometry ambiguity and native errors.
- [ ] Run focused Python tests and commit the bridge.

### Task 2: VS Code source publisher

**Files:** `extensions/lmemm-source/package.json`, `extension.js`, `bridge.js`, `bridge.test.js`.
**Interfaces:** explicit connect/pause/stop/note commands, grant file and per-client event/ack files from Task1. Pure `visibleSnapshot(editor,roots)` reads approved visible ranges only.
- [ ] Write Node tests for bounded UTF8 excerpts, focused/trusted/local/source checks, background editor not accessed, root containment and exclusions. Observe RED.
- [ ] Implement CommonJS extension using VSCode API and Node built-ins only; atomic0600 event writes,2second polling, private grant checks and native ack binding before text publication.
- [ ] Emit changed-document/view content only; unchanged heartbeat has no source text. Focus loss/pause/stop clears queued text. Intentional note command validates current source before/after user input.
- [ ] Run `node --test extensions/lmemm-source/bridge.test.js`; commit source publisher.

### Task 3: Pilot lifecycle, budgets and recall

**Files:** `semantic_memory/live_pilot.py`, `scripts/live_project_memory.py`; targeted updates `store.py`, `inference.py`, `retrieval.py`; `tests/test_semantic_live_pilot.py`.
**Interfaces:** `Pilot.ingest`, `tick`, `pause`, `resume`, `close`; CLI `start --workspace ROOT... --data-dir DIR [--runtime-config FILE --experimental-model]`, `status`, `pause|resume|flush|stop`, `context --project ROOT --days2`, `delete-session`.
- [ ] Write failing tests for two projects through intake/episodes/context, unchanged dedup, pause/revocation during worker result, restart identity, quota across writers, read-only context and tentative labels.
- [ ] Implement asynchronous bounded worker; normalize extractor failures to unprocessed coverage, cancel stale jobs on lifecycle boundaries, create new extractor on resume and drain/stop without hanging.
- [ ] Apply conservative SQLite page caps with journaling/reclaim reserve plus scheduled retention. Pause budget failures visibly without deleting pins or ordinary capture data.
- [ ] Provide deterministic readable project context, tentative claims and source IDs/original quotes, plus private control/status files. Never treat file snapshots as completed changes/user decisions.
- [ ] Run semantic regression suite and commit the complete pilot flow.

### Task 4: Verification, independent review and live-test handover

**Files:** README, architecture, context, pilot runbook/handover, this plan.
- [ ] Run full Python163baseline plus new tests, Node tests, syntax and whole-branch diff checks. Native read-only focus smoke if permitted; no unrequested content capture.
- [ ] Obtain one independent whole-change review; reproduce important findings RED→GREEN and rerun affected checks.
- [ ] Document exact local service/extension/pilot start/context/stop commands, existing failed model acceptance, approved scope and resource limits.
- [ ] Provide user live test across two approved projects, app/window switches, exclusions, pause/resume, restart and deletion. Keep real live results pending until user completes the run.
- [ ] Commit verified implementation/docs. Push only after live-test confirmation and handover; no main merge.
