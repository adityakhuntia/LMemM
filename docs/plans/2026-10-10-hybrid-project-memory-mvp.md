# Hybrid Project Memory MVP Implementation Plan

Execution update (2026-10-11): backend/service/native UI/MCP implementation is on local main, explicitly authorized by the user. Automated and synthetic integration evidence is in the hybrid-memory runbook and acceptance report. Original live crash, physical sleep/lock, paired 30-minute resources, real extension enrollment and external testers remain pending; unchecked live acceptance steps are not passes. The independent whole-implementation review and one material-finding regression/fix pass are complete; see the durable review-and-decisions record.


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task, preserving the user's native execution choice, followed by one independent whole-branch review. Steps use checkbox (`- [ ]`) syntax for tracking. Read the approved spec and this plan before implementation.

**Goal:** Deliver project-scoped hybrid evidence retrieval through the existing native Overview / Memory tabs and one read-only MCP agent, with exact citations and a verified resume workflow.

**Architecture:** Extend the existing SQLite semantic core with permission-aware chunks, FTS and versioned local embeddings. One supervised service owns writes and retrieval; the existing VS Code bridge supplies permitted visible evidence, while a reconciliation adapter mirrors eligible native notes. Native UI and a stdio MCP adapter consume the same authorized backend contracts over a private Unix socket.

**Tech Stack:** Existing Python 3.11 environment, SQLite/FTS5, NumPy, PyObjC/AppKit, VS Code JavaScript extension, unittest and Node built-in tests. Start with SQLite float32 vector blobs and exact cosine search over authorized candidates; avoid a vector server. The local embedding runtime/model is selected by Task 4's benchmark. Pin a maintained MCP SDK in Task 12 using its then-current official documentation.

**Spec:** [Approved hybrid project-memory MVP](../specs/2026-10-10-hybrid-project-memory-mvp.md), approved by the user after local spec commit `a0dfe69`. User approved this plan after commit `8ae1d6e`; native execution is in progress.

## Global Constraints

- Original isolation was `.worktrees/semantic-project-memory`, branch `feat/semantic-project-memory`. The user subsequently explicitly authorized direct commits on up-to-date main; the root checkout is now active. Preserve local context.md; do not add .env, capture data, models or grants.
- Sources: approved VS Code visible local-file excerpts and newly enrolled intentional project notes only. No repository crawl, browser/terminal intake, historical OCR or historical note import.
- One canonical workspace root per linked UI project; automatic artifact membership, no title-based identity or automatic project merges.
- Local embedding/inference only, no hosted fallback. Explicit model installation and separate agent disclosure authorization.
- Existing source limits: 4 KiB spans, 16 KiB envelopes. Capture must not wait for indexing/inference.
- 30-day evidence retention; 250 MiB semantic budget INCLUDING vectors, FTS, SQLite side files, bridge buffers and job metadata. Model weights are separate.
- One bounded model job at a time; pending payload at most 8 episodes/128 KiB; durable backlog contains source IDs, not repeated text.
- Up to 50 authorized keyword + 50 authorized vector candidates, at most 10 primary results + 10 one-hop supporting evidence entries. No cross-project search.
- Query <=2 KiB UTF-8; packets <=16 KiB; each citation resolution returns at most one retained span. Revalidate project/source/policy at every boundary.
- Time choices: Last 2 days (default), Last 7 days, All retained. Open tasks may predate the period; mark their dates.
- AppKit on the main UI thread; no self-process AX inspection. No IPC/model work on the UI event loop.
- Pause stops intake/model work and permits existing authorized keyword recall; never restart a model while paused. Quit stops the supervised service. Lock/sleep requires explicit intake resume.
- Model/claim failure must not suppress searchable evidence. Default packets contain only supported claims; no inferred completion, authorship or intent.
- Target: <=3 GiB additional runtime peak, <=150 MiB non-model overhead, <=2% additional idle CPU, warm search p95 <=2 seconds at 10,000 chunks; unloaded/cold latency reported separately.
- Latest existing verification: 693 Python tests and 6 Node bridge tests. These do not verify any new task in this plan.

## Review Focus

1. App UI becomes foreground while background AX readers run: no self-inspection or native abort (Tasks 1, 8, 13).
2. Two roots have the same basename, or a UI project is renamed/moved/merged: preserve exact scope and block incompatible merges (Tasks 2, 9).
3. Notes change or a source is revoked while a query/model job is running: no stale task state or deleted snippets (Tasks 3, 7, 9, 12).
4. Shared text, Unicode splitting and interrupted model upgrades: retain exact citation offsets without mixing ownership or dimensions (Tasks 3–5, 7).
5. User switches project/query while a slow response arrives or service restarts: never render stale results under a new project (Tasks 8, 10–12).

## File ownership and integration map

New modules are proposed paths, not existing implementations. Keep native drawing separate from read models and service logic; do not broadly refactor tracker.py/window.py.

| Unit | Files | Responsibility |
|---|---|---|
| Contracts and upgrades | `semantic_memory/contracts.py`, new `api_contracts.py`, `migrations.py`; existing `store.py` | Versioned request/result types, schema upgrade |
| Scope | new `semantic_memory/project_scope.py`, `grants.py` | Workspace/UI mapping, policy and client authorization |
| Retrieval | new `chunks.py`, `embedding_runtime.py`, `vector_index.py`, `index_worker.py`, `search.py`, `context_service.py`; existing `retrieval.py`, `relationships.py`, `retention.py` | Evidence indexing, retrieval, graph expansion, packets |
| Service | new `semantic_memory/service.py`, `ipc.py`, `scripts/project_memory_service.py`; existing `live_pilot.py`, `live_bridge.py`, `live_focus.py` | Single writer, native lifecycle, private transport |
| Native integration | new `src/memory_client.py`, `memory_notes.py`, `memory_model.py`, `memory_view.py`; existing `tracker.py`, `config.py`, `page_model.py`, `window.py`, `project_actions.py` | Supervisor, note reconciliation, project tabs and source drawer |
| Model evaluation | new `scripts/evaluate_memory_retrieval.py`, fixtures `tests/fixtures/project_memory/retrieval-v1/` | Frozen questions, retrieval/ranking/resource comparison |
| Agent | new `semantic_memory/mcp_server.py`; `requirements.txt` | Three tools, stdio transport, scoped connection |
| Release | new `scripts/benchmark_memory_mvp.py`, `docs/hybrid-memory-runbook.md` | Reproducible setup and acceptance evidence |

## Shared contracts (defined in Task 2)

Use immutable dataclasses in `api_contracts.py`; JSON serialization validates unknown fields, lengths and versions. IDs are strings, time bounds are UTC ISO strings, and filesystem roots are canonical paths. Existing `SourceEnvelope`/`SourceScope` remain source contracts; do not treat app scope as project permission.

- `ProjectBinding(ui_project_id, project_id, workspace_root, enrolled_at, active)`.
- `Grant(id, client_id, project_ids: frozenset[str], source_scope: SourceScope, revision: int, revoked: bool)`; UI session has a distinct owner grant, not an agent grant.
- `Query(project_id, text, start, end, limit=10)`; `RequestContext(grant_id, policy_revision)` is resolved server-side from capability, never trusted from a caller payload.
- `EvidenceHit(chunk_id, citation_id, artifact_id, locator, at, origin_type, text, truncated, score, related_to: str|None)`.
- `SearchResult(project_id, policy_revision, primary: tuple[EvidenceHit,...], related: tuple[EvidenceHit,...], coverage: dict, mode: str)`.
- `ContextResult(project_id, policy_revision, start, end, decisions, open_tasks, recent_evidence, unknowns, citations, coverage)`; bounded deterministic serialization shared by preview and MCP.
- `SourceDetail(project_id, citation_id, text, locator, at, origin_type, truncated, can_open_file)`.
- `MemoryStatus(state, reason, indexed_at, enrolled_at, pending, failed, model_state, retained_start, bytes_used)`.
- `ModelManifest(model_id, digest, dimension, max_input_tokens, chunk_version, runtime, weights_path)`; local path and pinned digest only, no caller-supplied endpoint.
- `NoteSnapshot(note_id, revision, project_id, text, created_at, done_at, deleted, origin)` and `SyncResult(applied, pending, rejected)`.

No cross-project tool is added. Builder may add internal fields when necessary but must keep serialized v1 contracts stable or explicitly version them.

## Commands and execution discipline

All commands below run from the feature worktree. Targeted unit tests:
`PYTHONPATH=src:tests ../../.venv/bin/python -m unittest TEST_MODULE -v`.
Full suite: `PYTHON=../../.venv/bin/python ./scripts/test.sh`.
Native AppKit/Vision tests need approved macOS framework access. Record that separately from sandbox limitations. Node: `node --test extensions/lmemm-source/bridge.test.js`.

Each task follows RED → minimal implementation → GREEN → explicit file staging and a local commit. Do not stage data or use `git add .`. Preserve user changes between tasks. Run the full suite at integration boundaries (Tasks 8, 11, 12, 13), not after every small edit. Test helpers named in snippets are built in the owning test module or `tests/memory_helpers.py`; they use temporary directories, deterministic embeddings and fake clocks, never personal evidence.

## Task 1: Establish native stability and acceptance fixtures

**Files:** existing `tests/test_self_accessibility.py`, `src/ax.py`, `src/trail_mac.py`; create `docs/benchmarks/project-memory/hybrid-mvp/baseline.md`, `tests/fixtures/project_memory/retrieval-v1/manifest.json` and `tests/memory_helpers.py`.
**Interfaces:** consumes current `11f5f3e` self-AX guard; produces baseline record and `make_memory_fixture(tmp_path, project_count=2)` test helper plus labelled query manifest format.

- [ ] Run the four self-accessibility regressions. Check any existing tracker before a user-approved live run; do not launch a duplicate.
- [ ] Repeat the user's original open-project/app-switch/pause/resume sequence with a private `-X faulthandler` log; include close/reopen, lock/sleep and explicit resume. Record actual result and first failing native trace. Fix a reproduced failure through its own failing regression before proceeding to integrated UI testing; do not claim the previous guard fully resolved the abort without evidence.
- [ ] Record baseline tracker CPU/RSS/disk with Memory absent; keep raw personal logs ignored and publish only aggregate measurements.
- [ ] Define >=40 labelled questions over two workspaces/two sessions, >=20 frozen held-out queries including >=10 paraphrases. Record gold occurrence IDs, dates, scope, no-evidence cases and source provenance. Keep development/held-out hashes distinct. Fixture includes same-title files, superseded content, explicit decision/task notes and an unrelated page never ingested.
- [ ] Validate fixture IDs/labels and commit only fixtures/helpers/aggregate baseline. Suggested commit: `test: establish hybrid memory acceptance fixtures`.

## Task 2: Versioned storage, project binding and grant scopes

**Files:** create `semantic_memory/api_contracts.py`, `migrations.py`, `project_scope.py`, `grants.py`, `tests/test_memory_scope.py`, `tests/test_memory_migrations.py`; modify `store.py`, `contracts.py` only where adapters require it.
**Interfaces:** `migrate(connection) -> None`; `bind_project(store, ui_project_id, root, at) -> ProjectBinding`; `resolve_binding(store, ui_project_id) -> ProjectBinding|None`; `authorize(store, grant_id, project_id) -> RequestContext`; `enroll_grant(store, client_id, project_ids, source_scope) -> Grant`; `revoke_grant(store, grant_id) -> int` (new revision).

- [ ] Add failing tests for preserving v1 evidence on upgrade, rollback on interrupted migration, schema-version rejection, unique mapping and permission refusal. Assertions:
```python
assert bind('ui-a', '/a/repo').project_id != bind('ui-b', '/b/repo').project_id
assert rename_ui('ui-a', 'New name').project_id == binding_a.project_id
assert denied_project_error == unknown_project_error
assert upgraded.evidence(ids) == original_evidence
```
- [ ] Run `test_memory_scope test_memory_migrations`; expect missing APIs/schema failure.
- [ ] Implement the dataclasses above and transactional schema migration from v1 to v2. Add binding/grant/note-mirror/index tables through migrations; model dimensions stay in generation metadata. Make read-only opening accept the supported migrated version. Reject partial/unversioned schemas. Bind canonical approved roots, not display names. Persist grant revision and source scopes; resolve capabilities to server-owned grant IDs.
- [ ] Run targeted tests and existing `test_semantic_store test_semantic_retrieval test_semantic_review_regressions`. Test symlink/relative root normalization and unrelated Python app identity separately from same-process exclusion.
- [ ] Stage named files and commit: `feat: add project-bound memory scopes and schema upgrades`.

## Task 3: Citable chunks and scoped keyword retrieval

**Files:** create `semantic_memory/chunks.py`, `search.py` (keyword component), `tests/test_memory_chunks.py`, `tests/test_memory_keyword.py`; extend `migrations.py`, `store.py`.
**Interfaces:** `index_source(store, source_id) -> tuple[str,...]`; `keyword_candidates(store, ctx, query, limit=50) -> list[EvidenceHit]`; `resolve_source(store, ctx, project_id, citation_id) -> SourceDetail|None`.

- [ ] Add failing tests for UTF-8 boundaries, original offsets, duplicate text with different owners, edited revisions, source deletion and query escaping. Use 1024-byte chunk target, <=128-byte overlap, breaking at paragraphs/whitespace when possible, never splitting a code point; tokenizer limits may require a versioned smaller chunk size in Task 4.
```python
assert original[start:end] == chunk.text  # offsets are Unicode character indices
assert sum(len(h.text.encode()) > 4096 for h in hits) == 0
assert all(h.citation_id in allowed_occurrences for h in results)
assert deleted_occurrence not in citation_ids(search('same shared text'))
```
- [ ] Run `test_memory_chunks test_memory_keyword`; expect missing index/search behavior.
- [ ] Add chunks with occurrence links and exact source offsets, plus chunk FTS5. SQL joins to authorized project/source/time before LIMIT; use parameterized queries and literal token handling, never accept raw SQL/FTS operators as instructions. Dedupe text for ranking while preserving authorized occurrence alternatives. Source resolution validates project ownership, current policy and tombstones.
- [ ] Run targeted tests plus `test_semantic_deletion_integration`. Pin empty/punctuation-only queries and 2 KiB limits with understandable errors. Check multiple matching occurrences and retained earlier file versions.
- [ ] Commit: `feat: index permitted evidence chunks for keyword recall`.

## Task 4: Local embedding backend and model selection

**Files:** create `semantic_memory/embedding_runtime.py`, `tests/test_memory_embeddings.py`, `scripts/evaluate_memory_retrieval.py`; extend retrieval fixtures and `requirements.txt` only if needed; create `docs/benchmarks/project-memory/hybrid-mvp/model-selection.md`.
**Interfaces:** `EmbeddingBackend.embed(texts: tuple[str,...], *, query: bool) -> numpy.ndarray`; `EmbeddingBackend.cancel() -> None`; `load_backend(manifest: ModelManifest) -> EmbeddingBackend`; `validate_manifest(manifest) -> None`. Matrix shape is (len(texts), dimension), finite float32, L2-normalized. Fake backend lives in test helpers.

- [ ] Write tests for fixed dimensions/normalization, finite values, explicit query/document prefixes, token overflow, cancellation, digest mismatch and no remote fallback:
```python
assert vectors.shape == (2, manifest.dimension)
assert np.allclose(np.linalg.norm(vectors, axis=1), 1)
assert invalid_or_remote_manifest_is_rejected()
assert cancelled_request_commits_nothing()
```
- [ ] Run `test_memory_embeddings`; expect missing backend/validation failures.
- [ ] Consult official model/runtime documentation at execution time; compare at least two small local embedding candidates against development queries on the target Mac. The evaluator embeds development fixtures into a temporary in-memory matrix and compares them with Task 3 keyword results; it does not depend on the Task 5 index worker. Reuse the cloud-disabled local runtime where suitable. Implement ONE production adapter after selection; benchmark adapters need not become supported product features. Pin model digest, dimension, tokenizer limit, license, prefix convention and measured download/runtime size in the report/manifest. Never truncate inputs invisibly.
- [ ] Run contract tests and development retrieval/resource comparison; select the smallest configuration with a credible path to the approved gates. If neither fits, stop model enablement and report the failed gate rather than changing privacy/budgets silently. User-approved installation is explicit; ordinary startup never downloads assets.
- [ ] Commit adapter, fixture/scoring code and metadata report, excluding downloaded weights/configured personal paths: `feat: add benchmarked local evidence embeddings`.

## Task 5: Incremental vector generations and bounded indexing

**Files:** create `semantic_memory/vector_index.py`, `index_worker.py`, `tests/test_memory_index_worker.py`, `tests/test_memory_vector_index.py`; extend `migrations.py`, `retention.py`.
**Interfaces:** `schedule_source(store, source_id) -> None`; `IndexWorker(store, backend).run_one() -> bool`; `vector_candidates(store, ctx, query, query_vector, limit=50) -> list[EvidenceHit]`; `begin_generation(store, manifest) -> str`; `activate_generation(store, generation_id) -> None`.

- [ ] Tests fail for repeated indexing, permission changes during inference, mixed model versions, paused workers, interrupted rebuild and queue caps:
```python
assert embed_calls_after_unchanged_replay == embed_calls_before
assert deleted_source not in committed_index_sources
assert vectors_compared_from_other_generation == 0
assert max_concurrent_model_jobs == 1
assert pending_payload_bytes <= 128 * 1024
```
- [ ] Run `test_memory_index_worker test_memory_vector_index` and confirm RED.
- [ ] Store normalized float32 vectors keyed by text/model/chunk version, linked through chunks to owned occurrences. Score only SQL-selected authorized chunk IDs, in bounded NumPy batches; never load an unbounded whole-corpus matrix. Persist ID-only job backlog and single-runner ownership. Prioritize query work between jobs, cancel jobs on pause/revocation, revalidate source/policy before commit. New generations rebuild within existing quota; keyword-only until a complete generation switches atomically.
- [ ] Run tests and a 10,000-chunk synthetic memory probe. Include zero vectors/dimension mismatches, low disk/quota, shared text and deletion during rebuild. Do not activate an index marked incomplete.
- [ ] Commit: `feat: add incremental bounded vector indexing`.

## Task 6: Hybrid ranking, graph expansion and shared context packets

**Files:** extend `semantic_memory/search.py`, `retrieval.py`, `relationships.py`; create `context_service.py`, `tests/test_memory_hybrid.py`, `tests/test_memory_context.py`.
**Interfaces:** `search_project(store, backend, ctx, query) -> SearchResult`; `get_context(store, ctx, project_id, start, end) -> ContextResult`; `render_packet(result) -> bytes` (<=16 KiB). These are the only result composers for UI/MCP.

- [ ] Add deterministic ranking/packet tests with fixed fake vectors and exact gold IDs:
```python
assert len(result.primary) <= 10 and len(result.related) <= 10
assert result_for_paraphrase.primary[0].citation_id == expected_source
assert unrelated_project_ids.isdisjoint(returned_project_ids)
assert len(render_packet(packet)) <= 16384
assert 'Reason not recorded' == unsupported_reason
```
- [ ] Run `test_memory_hybrid test_memory_context`; expect absent fusion/packet behavior.
- [ ] Fuse up to 50+50 candidates using RRF with k=60; deduplicate and tie-break deterministically by timestamp then ID. Calibrate irrelevant-result handling on development questions only; keyword-only mode when paused/model absent. Expand one supported hop using belongs_to/supports/references, never similarity or out-of-scope paths. Context uses exact retained evidence, explicit supported claims, older still-open tasks and bounded coverage. Preserve original source attribution. Resolve relative reference paths only to already-permitted captured artifacts.
- [ ] Run tests plus prior retrieval/state/relationship regressions. Test contradictory and superseded notes, missing reasons, observed TODO versus intentional TODO, stale task transitions, empty evidence and no-evidence questions. No new generative summarizer.
- [ ] Commit: `feat: combine semantic recall with supported project context`.

## Task 7: Complete index lifecycle, privacy and quota enforcement

**Files:** modify `semantic_memory/retention.py`, `grants.py`, `context_service.py`, `index_worker.py`, `store.py`; create `tests/test_memory_revocation.py`, `tests/test_memory_budget.py`.
**Interfaces:** `revoke_project(store, project_id) -> int`; `delete_memory_source(store, source_id) -> None`; `memory_usage(store, bridge_dir) -> dict`; extend existing `enforce_budget` and `delete_session` without bypassing graph support cleanup.

- [ ] Write barrier-based concurrency tests (events, not timing sleeps) that revoke/delete between ranking, expansion and return, and between embedding and commit:
```python
assert private_canary not in serialized_results_or_citations
assert not resolves(deleted_source_citation)
assert still_resolves(other_owner_same_text_citation)
assert pinned_over_budget.state == 'Needs attention'
```
- [ ] Run `test_memory_revocation test_memory_budget`; confirm all index/citation surfaces are exercised, not just intake.
- [ ] Invalidate policy and cached snapshots synchronously, tombstone source identity, cascade FTS/vector/graph/jobs and reclaim shared blobs only without surviving owners. Count journals, generations, bridge buffers and queues in 250 MiB; reserve migration/rebuild overhead. Stop ingestion if pinned data prevents reclamation. Bound SQLite temp/matrix memory. Final result serialization checks policy revision. Grant revocation removes access without necessarily deleting retained user data.
- [ ] Run existing retention/privacy suites and new tests for grant narrowing, same-text ownership, epoch changes, quota exhaustion and startup reconciliation. Never call deletion on system folders; preserve existing macOS guard.
- [ ] Commit: `fix: enforce memory deletion across indexes and query races`.

## Task 8: Single-writer service, private IPC and native supervisor

**Files:** create `semantic_memory/service.py`, `ipc.py`, `scripts/project_memory_service.py`, `src/memory_client.py`, `tests/test_memory_service.py`, `tests/test_memory_ipc.py`; modify `live_pilot.py`, `live_focus.py`, `src/config.py`, `tracker.py` only at lifecycle seams.
**Interfaces:** `MemoryService(data_dir, owner_grant, backend_factory).tick()/close()`; `serve_request(capability, method, params) -> dict`; `MemoryClient.start()/request(method, params, request_id)/poll()/stop()`; Status responses use `MemoryStatus`. Owner-only methods include enroll, model_install, pause/resume, note reconciliation and revoke; agent allowlist contains only three read methods.

- [ ] Add subprocess tests using fake native focus/backend: startup lock, two launch attempts, owner/agent capabilities, oversized/malformed requests, socket permissions and stopped parent:
```python
assert socket_mode == 0o600 and socket_parent_mode == 0o700
assert second_writer_refused
assert agent_call('enroll', {}).error == 'unavailable'
assert model_calls_while_paused == 0
assert service_unavailable_after_app_quit
```
- [ ] Run `test_memory_service test_memory_ipc`; confirm RED without launching real capture.
- [ ] Use schema-versioned length-prefixed JSON over AF_UNIX, 64 KiB request/frame cap, 16 KiB result packet cap, per-client secrets stored privately and server-side request contexts. Main service loop owns native focus/lifecycle; background workers handle I/O/indexing. Reuse bridge protections; refactor Pilot only enough to inject store/lifecycle orchestration. Parent uses async requests plus main-thread completion polling, retains subprocess ownership, waits for READY and reconciles before exposing queries. App quit cancels jobs and closes child; unexpected parent death closes child via control-channel EOF. Restart is explicit after crash, with bounded failure reporting.
- [ ] Run full Python + Node suites. Test service and parent PID exclusion, no self-read from native callbacks, UI responsive during delayed backend, model missing -> keyword-only, and sleep/resume. Preserve the original standalone pilot as an explicitly experimental command, with exclusive store lock.
- [ ] Commit: `feat: supervise a private project memory service`.

## Task 9: Project enrollment and durable native-note synchronization

**Files:** create `src/memory_notes.py`, `tests/test_memory_note_sync.py`, `tests/test_memory_project_actions.py`; modify `tracker.py`, `project_actions.py`, `projects.py`, `notes.py`, `semantic_memory/service.py`, `project_scope.py`, `grants.py`; extend extension acknowledgments only if needed.
**Interfaces:** `project_memory_action(action, ui_project_id, root=None) -> ProjectBinding|None`; `begin_note_mutation(project_id, mutation_id) -> None`; `reconcile_notes(project_id, snapshots: tuple[NoteSnapshot,...], mutation_id) -> SyncResult`; `project_snapshot(items, binding, enrolled_at) -> tuple[NoteSnapshot,...]`.

- [ ] Tests for note save/done/reopen/delete, same-note replay, ambiguous OCR association, pre-enrollment notes and parent crashes:
```python
assert claims_after_replay == claims_before_replay
assert ambiguous_note not in semantic_sources
assert old_note not in semantic_sources
assert pending_note_project_context.open_tasks == []
assert resume_after_reconcile.open_tasks == expected_tasks
```
- [ ] Run `test_memory_note_sync test_memory_project_actions`; expect missing integration.
- [ ] Enroll one root per UI project with automatic file association; block merging linked projects, preserve rename/move, expose archive versus revoke semantics. For native note mutation: persist a service-side read fence for affected note-derived claims, save the normal JSON authority, then reconcile stable IDs/revisions and clear the fence. If service is offline, mark durable pending sync in the native adapter and reconcile before service READY; never serve an old live mirror. A crash after fencing leaves claims hidden until reconciliation. Delete/revoke tombstones before success. Source content and occurrence ownership remain canonical in one authority per origin. Mirror only new explicitly project-scoped notes; no inferred foreground-title membership. Provide a project-note save action in Memory, not a requirement to open a tracked item first.
- [ ] Test write failure before/after each boundary, service restart, deleted-source replay, failed text updates and task edits that cease to be TODOs. All native note mutation entrypoints including CLI controls use the adapter; unresolved notes stay Overview-only. Verify independent user-note references for explicit decision/reason extraction.
- [ ] Commit: `feat: connect project enrollment and native notes to memory`.

## Task 10: Memory read model and asynchronous navigation

**Files:** create `src/memory_model.py`, `tests/test_memory_model.py`; modify `page_model.py`, `window_model.py`, `memory_client.py` and relevant existing model tests.
**Interfaces:** `new_memory_state() -> dict`; `memory_reduce(state, action, payload) -> dict`; `memory_view(state, binding, status, result) -> dict`; actions tab/select_project/query/submit/time_filter/source/preview/response/cancel, each request carrying generation + project + request ID.

- [ ] Add model tests for exact labels, selected-tab history, enrollment states, asynchronous results and scope changes:
```python
assert tabs == ['Overview', 'Memory']
assert state_after_typing.request_count == 0
assert state_after_return.request_count == 1
assert late_project_a_response_not_shown_in_project_b
assert paused_status_keeps_keyword_results
```
- [ ] Run `test_memory_model` and confirm RED.
- [ ] Implement deterministic read model: Last 2 days/Last 7 days/All retained, decisions/tasks/recent evidence without query, ranked results with query, source drawer and coverage copy. Keep sidebar search semantics unchanged. Expired/unavailable citations differ from empty evidence; unsupported claims never produce 'All caught up'. Track service/index generation and discard late responses; clear inaccessible results on revocation. The UI never sorts a raw vector score into a claimed confidence badge.
- [ ] Run existing page/window/key navigation tests plus new cases for Unicode queries, empty periods, missing model, error preserving permitted prior results and revoked grants clearing prior results.
- [ ] Commit: `feat: model project memory tabs and evidence navigation`.

## Task 11: Native Memory tab, source drawer and setup

**Files:** create `src/memory_view.py`, `tests/test_memory_view.py`; modify `window.py`, `tracker.py`, `settings_model.py`, `memory_client.py`; extend `tests/window_smoke.py` and add native scenario notes in `docs/hybrid-memory-runbook.md`.
**Interfaces:** `MemoryPane(parent, on_action).render(view)/layout(rect)`; callback routes model actions, not SQL/native filesystem reads. Existing MainWindow owns tab navigation and main-thread updates; dedicated pane owns Memory subviews.

- [ ] Add drawing/action tests for every state, keyboard focus, source detail and explicit installation/enrollment; fake AppKit tests must verify action wiring, not merely lack of exceptions:
```python
assert source_click.args == (project_id, citation_id)
assert displayed_snapshot == retained_text
assert 'today' in open_file_explanation.lower()
assert denied_local_path_open_count == 0
```
- [ ] Run `test_memory_view test_window_smoke`; confirm missing tab/drawer actions fail.
- [ ] Add tabs, project path/status, project-note entry, submit-on-Return search, period control, deterministic resume sections and source drawer. Open file only after canonical permitted-path check and explicit click; display retained snapshot separately. Setup enrolls workspace and installs selected model after showing measured size/location; reconnects the existing extension via fresh grant with explicit user action. Package the VS Code extension for normal installation rather than requiring a development host. Settings expose Memory enable/pause and agent connection entrypoint. Preserve existing fonts/styles and VoiceOver labels; capture grants are not inferred from agent setup.
- [ ] Run full suites and user-approved native smoke: disabled/setup/ready/processing/paused/error, tabs/search/keyboard/source/open-file and two-window app switching. No model call on UI thread. Record screenshots using consented synthetic sources and link them as UI evidence in the runbook; automated fake views are not native acceptance.
- [ ] Commit: `feat: add native project memory and source inspection`.

## Task 12: Read-only MCP and grant-specific context preview

**Files:** create `semantic_memory/mcp_server.py`, `tests/test_memory_mcp.py`, `tests/test_memory_preview.py`; modify `service.py`, `ipc.py`, `memory_model.py`, `memory_view.py`, `requirements.txt`; add connection instructions to `docs/hybrid-memory-runbook.md`.
**Interfaces:** tool signatures exactly match spec: `search_project_memory(project_id, query, start=None, end=None, limit=10)`, `get_project_context(project_id, start=None, end=None)`, `resolve_citation(project_id, citation_id)`. UI preview calls the same `get_context` function with the selected configured grant and normalized time bounds. Proposed-grant preview is read-only and never persists a capability.

- [ ] Add integration tests with actual stdio framing using the selected SDK; no hand-rolled incomplete MCP protocol. Test allowlisted tools, time normalization, limits, hostile evidence and preview parity:
```python
assert normalize(preview_packet) == normalize(mcp_packet)
assert no_write_tools_exposed
assert denied_error == unknown_error
assert other_project_citation_unavailable
assert serialized_packet_bytes <= 16384
```
- [ ] Run `test_memory_mcp test_memory_preview`; expect absent adapter/preview.
- [ ] Verify current official SDK/client docs, pin dependency, implement a thin stdio adapter forwarding only the three read requests through its grant. Secret paths/tokens never appear in tool arguments/logs. Connection setup explicitly authorizes project/source scopes and explains hosted-agent disclosure. Preview displays the exact normalized packet plus scope/revision, with citation actions and explicit copy. Proposed preview is labelled; no grant or transmission occurs simply by previewing.
- [ ] Run full suites, actual stdio protocol test and one consented Codex project-resume test. Confirm service unavailable on quit, paused keyword-only behavior, revoked-client refusal, empty coverage and exact evidence links. Any client-specific setup uses current supported configuration, not assumed stale docs.
- [ ] Commit: `feat: expose scoped project memory through MCP and preview`.

## Task 13: Fresh retrieval, assertion, lifecycle and resource acceptance

**Files:** extend `scripts/evaluate_memory_retrieval.py`; create `scripts/benchmark_memory_mvp.py`, `tests/test_memory_acceptance.py`, `docs/benchmarks/project-memory/hybrid-mvp/acceptance.md`; finalize `docs/hybrid-memory-runbook.md`.
**Interfaces:** evaluator takes frozen manifest/model/index hashes and outputs machine-readable counts + aggregate report; benchmark compares baseline versus enabled service on the same workload. Public reports contain synthetic/consented aggregate evidence, not captured personal text.

- [ ] Write harness tests that detect contaminated held-out split, empty/duplicate gold labels, false success with no claims, missing source citations and resource samples from an unloaded model. Run `test_memory_acceptance` and confirm failing conditions.
- [ ] Implement scoring: Recall@5 and MRR for keyword-only/vector-only/hybrid; >=80% hybrid Recall@5 overall, >=10 percentage-point paraphrase gain over keyword-only and no exact-identifier Recall@5 regression. Assert default claims >=95% precision and zero unsupported decisions/reasons/completions on fresh labels; report recall, omissions, denominators and experimental-disabled modes. Do not retune on held-out data; create a new split after material changes.
- [ ] Run zero-leak checks across every output surface and races: two same-name projects, shared text, revoked grants, deleted sessions, interrupted jobs/rebuilds, stale UI results, incomplete note reconciliation and malicious source instructions. Repeat the native crash sequence, restart, pause/resume and sleep/lock acceptance.
- [ ] Measure >=30 minutes representative enabled versus baseline work plus >=60 seconds idle. Verify warm p95 <=2 seconds at 10,000 authorized chunks, <=30-second searchable latency without backlog, <=3 GiB additional model/runtime peak, <=150 MiB non-model overhead, <=2% additional idle core CPU and 250 MiB semantic quota. Report cold start, device details, energy where available and measurement limitations; missing observations are not a pass.
- [ ] Run full Python + Node suites once after final changes; have a fresh independent whole-branch reviewer inspect authorization, lifecycle, native thread use and citation fidelity. Resolve material findings and rerun affected tests.
- [ ] Test the install/runbook with >=3 consented people outside implementation. Record their ability to enroll, query, inspect evidence and connect Codex, plus resume time/recap effort versus their usual workflow. If testers are unavailable, report that external-beta gate as pending rather than inventing acceptance.
- [ ] Commit code/harness and sanitized acceptance records: `test: verify hybrid memory beta acceptance`. Do not publish or claim launch complete while mandatory gates fail.

## Dependency order and two-week target

`1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13` is the safe native execution order. Fixture/model evaluation can be revisited between related tasks; frozen held-out results remain untouched until configuration is fixed. UI model work can use deterministic contract fixtures, but real rendering is not accepted until integrated service responses exist.

| Target days | Deliverable | Gate before moving on |
|---|---|---|
| 1–2 | Native retest, fixtures, scope/migrations, chunks | No unresolved native blocker; exact project/citation ownership |
| 3–5 | Embedding choice, incremental index, hybrid retrieval | Useful paraphrase retrieval and deletion-safe indexes |
| 6–8 | Service lifecycle, note sync, Memory model/view | User can enroll, search and inspect retained evidence |
| 9–10 | MCP + preview, first real agent resume | Same permitted context reaches UI and agent |
| 11–14 | Fresh evaluation, resource/lifecycle testing, external beta | All mandatory gates met, reviewer findings resolved |

These are planning targets, not evidence of capacity or a guaranteed deadline. Highest
risks: local model fit, current native stability, cross-store note reconciliation,
extension installation and measured resource use. If time slips, defer experimental
claim extraction and cosmetic polish. Do not cut source authorization/deletion,
citation inspection, hybrid retrieval or the actual agent-resume loop. Any change to
approved source scope, privacy or acceptance budgets goes back to the user.

## Self-review and handoff

- [x] Every spec section maps to tasks: source/project 2/3/9; runtime 4/5/8; hybrid 3–6;
  graph/claims 6/9; UI 10/11; MCP 12; deletion/budgets 7; acceptance 1/13.
- [x] Shared contracts and later interface names are consistent; proposed new files are
  explicitly identified. Existing classes/functions were inspected before planning.
- [x] Five review-focus conditions each have owning task tests; native tests and
  fixture/unit evidence are distinguished.
- [x] No product code, dependencies, model downloads, schema migrations or live capture
  were performed during planning. No historical successful test is treated as MVP acceptance.
- [x] User approved the plan; native implementation under executing-plans started.
