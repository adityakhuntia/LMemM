# Automatic Project Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (preserved native execution choice), or superpowers:subagent-driven-development if the user changes that choice. Implement task-by-task with test-first steps.

**Goal:** Build and evaluate an on-device semantic-memory core that automatically connects coding-project evidence and returns source-backed project-resume context.

**Architecture:** A separate SQLite store ingests permission-checked source envelopes, deduplicates text and forms bounded episodes. A single local inference worker proposes typed claims/relationships; deterministic policy controls support status, corrections, deletion and scoped retrieval. Begin with controlled fixtures; live adapters and MCP are separate increments.

**Tech Stack:** Python, standard-library SQLite/FTS5, unittest, a benchmark-selected local inference runtime. No hosted model or mandatory embedding/graph service.

**Spec:** [Approved automatic project-memory design](../specs/2026-10-07-automatic-project-memory-design.md).

## Execution status — 2026-10-07

Fixture-driven Tasks 1–6 have committed implementations with review fixes. Their
full acceptance checklists remain open where coverage or behavior is incomplete.
Task 7 tooling and two real local-model comparisons are implemented; neither model
passed. Task 8 regression/review/documentation work is verified (144 tests); real semantic
acceptance and remaining implementation items stay open. This is an isolated
engineering increment, not semantic acceptance or the live/MCP MVP. Detailed evidence
and remaining gaps: [implementation status](../semantic-project-memory-status.md).

## Global constraints

- On-device inference only; no hosted endpoint or network fallback. Model downloads never contain user content.
- VS Code plus permitted browser sites are the eventual live scope; no new live capture or editor adapter in this plan.
- Workspace/file identity must be authoritative; unknown identities remain tentative/unassigned. Manual attachment is optional correction.
- Source text spans at most 4 KiB; extraction evidence at most 16 KiB; candidate summaries at most eight.
- Close episodes on artifact change, five-minute gap, permission/pause boundary; flush at two minutes or 16 KiB.
- One inference worker; queue at most eight episodes/128 KiB. One bounded retry; failure leaves unprocessed evidence and visible coverage status.
- SQLite semantic schema is separate from the existing JSON memory index. Existing memories are not silently rewritten/imported.
- Durable evidence retention 30 days; raw semantic-source retention 24 hours/500 MiB; semantic budget 250 MiB including SQLite side files/indexes, excluding model weights.
- Optional pinned user notes/corrections count toward the budget and are never silently pruned. Pause ingestion if safe reclamation cannot meet budget.
- Benchmark gates: supported-association precision at least 95%, relevant-artifact recall at least 80%, zero unsupported decision/completion assertions and zero forbidden-source leakage in the evaluation suite.
- Resource gates: additional model/runtime peak RAM at most 3 GiB; other semantic overhead at most 150 MiB; idle CPU average at most 2% over 60 seconds; extraction p95 at most 30 seconds. These are approved targets, not established results.
- Preserve source attribution, unknown authorship, truncation and conflicts. Model self-confidence never establishes truth or ownership.

## Review focus

1. Source ID replay with different content/permissions must not mutate existing evidence (Task 1).
2. Identical text from allowed and revoked sources must preserve independent ownership and scoped citations (Tasks 1, 5).
3. Revocation/deletion while inference is running must prevent stale completion from restoring forbidden claims (Tasks 3, 5).
4. Observation text containing instructions/JSON must not control tools, permissions, inference configuration or graph writes (Tasks 3, 4).
5. Pinned evidence plus SQLite side files filling the budget must visibly pause ingestion without destroying pins or blocking capture (Task 5).

## Module boundaries

Create a `semantic_memory/` package: `contracts.py` (immutable envelopes/types), `policy.py` (scope/identity), `store.py` (transactions/schema), `episodes.py` (bounded episodes), `inference.py` (validation/scheduler), `relationships.py` (support/corrections), `retrieval.py` (context packet), `retention.py` (budgets/deletion), `local_runtime.py` (selected runtime adapter), `evaluation.py` (labelled scoring/benchmarks).

Use `data/memory/semantic.sqlite3` as the eventual default, accessed through a new `config.Paths.semantic_file` property. Tests and evaluation always pass temporary/disposable paths. Expose initial developer commands through `scripts/evaluate_project_memory.py`, not the tracking startup path. Normal `lmemm.py` startup must not load a model or begin semantic ingestion.

Tests: `tests/test_semantic_store.py`, `test_semantic_episodes.py`, `test_semantic_inference.py`, `test_semantic_relationships.py`, `test_semantic_retention.py`, `test_semantic_retrieval.py`, `test_semantic_evaluation.py`. Fixtures: `tests/fixtures/project_memory/` with development and held-out manifests. No fixtures copied from private `data/`.

### Task 1: Permission-checked evidence and transactional identity

**Files:** Create package initializer, `contracts.py`, `policy.py`, `store.py`; modify `config.py`; create `tests/test_semantic_store.py`.

**Interfaces:**
- Frozen `SourceEnvelope(source_id, at, session_id, app_id, artifact_locator, workspace_locator, identity_authoritative, origin_type, spans, policy_revision, private_context, browser_context_known)`; `TextSpan(span_id, text, truncated)`; `AccessPolicy(revision, allowed_apps, allowed_origins, denied_origins)`.
- `SourceScope(app_ids: frozenset[str], origins: frozenset[str])`, `Correction` and result/request/packet types live in `contracts.py`; define their fields from the consuming task's Interfaces before implementation of that task, avoiding cross-module duplicate types.
- `validate_source(envelope: SourceEnvelope, policy: AccessPolicy) -> SourceEnvelope`: reject invalid/forbidden envelopes, including stale revisions. UTF-8 byte bounds apply without splitting characters.
- `canonical_identity(envelope: SourceEnvelope) -> tuple[str | None, str | None]`: stable project/artifact IDs, never filesystem reads; distinguish normalized paths with identical basenames. Unsupported identities return null.
- `SemanticStore(path: Path)` creates version-1 schema/FTS5, enables foreign keys and private file permissions; `ingest(envelope, policy) -> IngestResult(source_id, occurrence_ids, project_id, artifact_id, inserted)` is transactional/idempotent.

- [ ] Write failing tests named `test_duplicate_source_is_idempotent`, `test_conflicting_source_replay_rejected`, `test_denied_private_unknown_browser_rejected`, `test_same_name_workspaces_do_not_merge`, `test_query_document_ids_preserved`, `test_shared_text_has_separate_occurrences`, and `test_unicode_span_byte_limit`. Assertions: duplicates add zero rows; changed replay raises; denial leaves no text/FTS rows; distinct locators yield distinct IDs; each source owns its citations.
- [x] Run `.venv/bin/python -m unittest discover -s tests -p test_semantic_store.py -v`; observe missing implementation failures.
- [x] Implement schema tables for projects/artifacts/blobs/occurrences/episodes/claims/edges/support/corrections/jobs and schema migration bookkeeping. Foreign keys own dependent rows. Exact original text is citation evidence; raw-text hash deduplicates blobs and normalized hash identifies equivalent content. Whitespace variants may retain separate original blobs rather than misquote a source.
- [x] Implement canonicalization and policy checks; FTS indexes unique retained text. Reject unsupported schema versions visibly. Define UTC aware timestamps and stable IDs; prohibit field/path injection and arbitrary file reads. Use a writer lock, parameterized SQL and explicit transactions.
- [ ] Run focused tests and existing config/storage tests; confirm pass. Commit this independently testable store.

### Task 2: Bounded work episodes and deterministic fixture corpus

**Files:** Create `episodes.py`, `tests/test_semantic_episodes.py`, fixtures and their manifest/README.

**Interfaces:**
- `EpisodeBuilder(store: SemanticStore)`; `accept(source_id: str) -> list[str]` returns newly closed episode IDs; `boundary(reason: str, at: str) -> list[str]`; `flush(at: str) -> list[str]`.
- `build_request(episode_id: str, candidate_limit: int = 8) -> EpisodeRequest`: ordered evidence/candidate IDs and bounded text. Episodes record omitted evidence and truncation explicitly.
- `load_fixture_manifest(path: Path) -> FixtureCorpus`: source envelopes, policy, expected associations/claims/resume packets and immutable development/held-out split.

- [ ] Write tests asserting exact five-minute-gap/two-minute-flush boundaries, artifact/pause/revision boundaries, 4/16 KiB limits, unchanged content producing no repeated extraction evidence, same content from different ownership retained, and restart restoring closed/unprocessed episodes without duplicates.
- [ ] Run episode tests; observe failures before implementing.
- [ ] Implement episode persistence and selection using Task 1 interfaces; FTS plus nearby anchored episodes yields at most eight candidate summaries. Unknown context never borrows an authoritative identity from the previous artifact. Bound candidates separately so summaries cannot expand requests without limit.
- [x] Create at least 24 labelled synthetic episodes across two coding projects. Assign eight held-out episodes before any model comparison. Cover interleaving, same titles, renamed locators, explicit/implicit tasks, unknown authorship, AI suggestions, decisions/reasons, conflicts and revoked/deleted sources. A renamed workspace without verified alias remains separate, not magically recognized.
- [ ] Run fixture validation and episode tests; confirm limits, split disjointness and every expected citation's existence. Commit episode formation plus corpus; no semantic-quality claim yet.

### Task 3: Safe structured extraction and bounded scheduling

**Files:** Create `inference.py`, `tests/test_semantic_inference.py`.

**Interfaces:**
- `LocalExtractor.extract(request: EpisodeRequest) -> str` protocol for local structured JSON, plus `cancel() -> None`; fake extractor only for deterministic tests.
- `validate_extraction(payload: str, request: EpisodeRequest) -> ExtractionResult`: typed candidates with supplied IDs only; no graph writes from raw model output.
- `InferenceWorker(store, extractor)`; `enqueue(episode_id: str) -> bool`, `run_one() -> JobResult`, `cancel_scope(scope: SourceScope) -> None`, `status() -> dict`.

- [ ] Write failing tests for malformed/oversized JSON, unknown evidence/entity IDs, source-origin attribution, source instructions requesting data export, one retry then unprocessed status, queue eight/128 KiB bounds, cancellation, restart and a source revision changed during extraction. Assert stale results cannot commit and no test executes model-provided commands.
- [ ] Run inference tests and observe failure.
- [ ] Implement strict candidate schema with bounded lists/strings, one worker and persistent job states. Requests contain data only; no tool execution. Queue entries hold bounded request metadata rather than unbounded retained copies. Revalidate current support and policy revision in the commit transaction. Timeout after 30 seconds per attempt; total attempts at most two. Mark timeout/resource failures and coverage gaps visibly.
- [ ] Pause/overload defers jobs in the store; it does not block capture or silently discard evidence. Cache only by evidence IDs/content hashes, policy revision and model configuration; invalidation follows source changes.
- [ ] Run tests; confirm pass. Commit extraction contract/scheduler. Fake-output tests verify engineering behavior, not actual semantic quality.

### Task 4: Automatic relationships and epistemic status

**Files:** Create `relationships.py`, `tests/test_semantic_relationships.py`.

**Interfaces:**
- `apply_extraction(store, episode_id: str, result: ExtractionResult) -> ApplyResult`: one transaction, with current source-policy revalidation.
- `apply_correction(store, correction: Correction) -> str`: action assign/reject/remove/complete/reopen, actor user, dated provenance; no model can impersonate a correction.
- `recompute_support(store, entity_ids: set[str]) -> None`: update relationship/claim status after evidence changes.

- [ ] Write tests asserting workspace containment gives supported code membership; tab switching or semantic similarity alone remains inferred; an explicit cited project/artifact reference can support browser membership; independent episode corroboration is required; general references may support multiple projects; rejected links stay rejected.
- [ ] Add tests for third-party/AI decision quotes, unknown authorship, absent reason, inferred task versus explicit commitment, disappearing-window non-completion, explicit done/reopen, contradictions and supersession. Unsupported model declarations must stay labelled candidates.
- [ ] Run relationship tests and observe failures.
- [ ] Implement typed edges and support rules from spec section 6. Deterministic text/source checks can reject unsupported assertions but do not guarantee semantic accuracy. Store extraction status and supporting spans; do not flatten status into model confidence. Preserve history and user corrections instead of destructive overwrites.
- [ ] Run relationship/inference/store tests; confirm pass and commit. Model correctness remains subject to Task 7's held-out gate.

### Task 5: Retention, source revocation and capture deletion integration

**Files:** Create `retention.py`, `tests/test_semantic_retention.py`; modify `input_store.py` deletion recovery only through a scoped optional semantic-store hook; add regressions in `tests/test_input_store.py`.

**Interfaces:**
- `delete_sources(store, source_ids: set[str]) -> DeletionResult`; `delete_session(store, session_id: str) -> DeletionResult`; `revoke_scope(store, scope: SourceScope, policy: AccessPolicy) -> DeletionResult`.
- `enforce_budget(store, now: str, raw_root: Path | None) -> BudgetStatus`; `BudgetStatus` exposes measured bytes, pruned counts, paused reason and coverage effects.

- [ ] Write tests for shared-text independent ownership, revoked-origin search/citation exclusion, last-support removal, pinned-budget exhaustion, 30-day evidence and 24-hour raw expiry, 250/500 MiB limits (inject smaller limits), pending extraction cancellation and a crash between semantic cleanup and existing capture-manifest completion.
- [ ] Run retention/deletion tests; observe failures.
- [ ] Implement transactional cleanup and FTS/cache/support invalidation, idempotent session deletion, a revocation revision barrier, and pruning of only unpinned eligible material. Measure DB plus WAL/SHM/journal files; perform bounded checkpoint/reclamation and refuse growth when budget cannot be met. Account for projected writes and SQLite page allocation headroom, not merely a daily file-size check.
- [ ] In existing `recover_deletion`, if `root/semantic.sqlite3` exists, invoke idempotent semantic session cleanup before removing the capture manifest. Never create a semantic DB during legacy deletion. Validate path containment; a cleanup failure leaves the manifest for retry. Existing deletion blockers still apply. No automatic legacy ingestion.
- [ ] Raw ownership is restricted to a dedicated semantic raw root; never prune ordinary capture/history files as though this new budget covered them. No model weights within raw pruning scope. In this fixture-only increment, raw images are optional and no screenshot collector is introduced.
- [ ] Run focused tests plus all existing provenance/deletion tests; confirm pass and commit integrated deletion/retention.

### Task 6: Scoped project-resume retrieval and deterministic rendering

**Files:** Create `retrieval.py`, `tests/test_semantic_retrieval.py`.

**Interfaces:**
- Consumes `SourceScope` from Task 1 and current policy/support state from Tasks 4–5.
- `project_context(store, project_id: str, start: str, end: str, scope: SourceScope) -> ContextPacket`; `resolve_citation(store, citation_id: str, scope: SourceScope) -> Citation | None`; `render_context(packet: ContextPacket) -> str`.
- `ContextPacket`: recent_changes, decisions, open_tasks, artifacts, conflicts, unknowns, citations and coverage; tentative links/tasks are separately labelled.

- [ ] Write project-resume tests for two days ago, multiple projects, interval boundaries, inferred exclusions, explicit reasons versus unknown reasons, current task done/reopen as of requested end, expired evidence, failed inference and revoked sources. Assert narrowing scope cannot reveal facts supported solely by forbidden sources or resolve their citations.
- [ ] Run retrieval tests and observe failures.
- [ ] Implement SQL-backed bounded retrieval: at most 20 entries per section, 40 citations, 16 KiB rendered context, with explicit omitted counts/truncation. Time-range claims use supporting evidence in the requested interval; task state is evaluated as of interval end using relevant prior explicit state evidence. Never cite outside authorized scope; permission is checked at read time as well as ingest.
- [ ] Render deterministic context without another model call. Unknown project/time errors are explicit; no private evidence interpolated into errors. MCP will call this same interface later.
- [ ] Run retrieval and deletion suites; confirm pass and commit project context output.

### Task 7: Real local-runtime benchmark and model selection

**Files:** Create `local_runtime.py`, `evaluation.py`, `scripts/evaluate_project_memory.py`, `tests/test_semantic_evaluation.py`; create `docs/benchmarks/project-memory/` result manifest and report during execution.

**Interfaces:**
- `RuntimeConfig(executable: Path, model_path: Path, arguments: tuple[str, ...], context_limit: int)` contains local file paths only, no endpoint or remote model ID.
- `LocalRuntime(config: RuntimeConfig)` implements `LocalExtractor`; startup fails if local assets are absent/unsupported. Use no shell evaluation and no dynamically executed model output.
- `evaluate(corpus: FixtureCorpus, extractor: LocalExtractor, split: str) -> EvaluationReport`; `benchmark(config: RuntimeConfig, corpus: FixtureCorpus) -> BenchmarkReport`.
- Script CLI: `--manifest PATH --runtime-config PATH --split development|heldout --output DIR`. Only controlled fixtures may be used until live prerequisites pass.

- [ ] Write scorer tests with known true/false positives, missing predictions, invalid citations and invented reasons; assert denominators and metrics. Test local-runtime missing assets, disallowed endpoint/config, malformed output, cancellation and timeouts with a fake executable. A fake benchmark must be labelled synthetic and cannot produce a passing real-model selection record.
- [ ] Run evaluation tests and observe failures; implement deterministic scoring and resource sampling, including process-tree peak RAM, worker/baseline overhead, latency, DB-side-file growth and 60-second idle CPU sample. Label unavailable energy metrics rather than fabricate results.
- [x] Inspect target hardware and research candidate runtimes/models using current official documentation/model cards. Shortlist at least two on-device configurations likely to fit 3 GiB additional RAM; record licence, weight hash, quantization, runtime version and expected context capacity before download/install. Preserve user-content offline constraint. Do not silently widen the memory budget.
- [ ] Select candidates using development data only; freeze prompt/configuration and scoring before held-out execution. Run real extraction on held-out data, record at least 30 extraction timings by repetitions for p95 (quality denominators remain unique examples), and measure baseline versus semantic-enabled resource use. Keep full failure/error counts.
- [x] Choose the smallest actual configuration meeting every quality/resource gate; record reproducible commands and measured results in the benchmark manifest. If none passes, stop runtime enablement and report failed criteria to the user; engineering tasks may be complete, semantic acceptance is not. No hosted fallback, automatic embeddings expansion or reinterpretation of lexical output as semantic success.
- [x] Run focused runtime/evaluation tests and commit benchmark tooling/report. Downloaded weights and private data remain ignored and uncommitted.

### Task 8: End-to-end evaluation, review and handover

**Files:** Existing/new test suites; `README.md`, `ARCHITECTURE.md`, `context.md`, this plan and benchmark report.

- [x] Run `.venv/bin/python -m unittest discover -s tests -v`, syntax compilation and `git diff --check`. Existing 110-test baseline remains passing alongside the new suite; do not weaken input/privacy checks to obtain a green run.
- [ ] Exercise actual fixture envelopes → store → episodes → selected local extractor → relationships → project context → delete/revoke → retrieve again. Verify repeat ingestion/restart is idempotent, budgets visible and forbidden evidence absent. Do not count injected outputs as real semantic validation.
- [x] Obtain one independent whole-change review using requesting-code-review, specifically adversarial sources, source ownership/deletion races, supported-status promotion, retrieval scope and resource bounds. Resolve important findings and rerun affected checks.
- [x] Update docs with implemented interfaces, reproducible evaluation, selected model only if benchmark passed, current limits and no live/MCP claim. Mark completed tasks in this plan; preserve any blocked benchmark/acceptance task as open.
- [ ] Commit the verified increment and report test counts, semantic metrics, resource results, publication state and remaining source/MCP prerequisites. Keep implementation isolated from main until reviewed; do not auto-merge an incomplete benchmark.

## Self-review and handoff

Written spec approved by user. Coverage: sections 3–4 → Tasks 1–2; extraction/relationships → Tasks 3–4, 7; storage/deletion → Tasks 1, 5; retrieval → Task 6; acceptance → Tasks 2, 7–8. Live access/capture/editor identity and MCP are explicitly separate follow-ups, not omitted implementations disguised as complete MVP.

Plan self-review complete; no product code or model installation has begun. Preserve native execution in this session followed by one independent review. Written-plan review is pending. During execution create an isolated feature branch/worktree and read both this plan and the approved spec.
