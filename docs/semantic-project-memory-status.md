# Semantic project-memory increment — 2026-10-07

Status: fixture-driven engineering core implemented on `feat/semantic-project-memory`
in `.worktrees/semantic-project-memory`. No accepted model, live semantic capture,
or MCP integration. Existing tracker behavior is unchanged.

## Flow and interfaces

`SourceEnvelope` + explicit `AccessPolicy` → `SemanticStore.ingest` →
`EpisodeBuilder` → bounded `EpisodeRequest` → `InferenceWorker` / `LocalRuntime`
→ validated candidates → deterministic relationship policy → scoped
`project_context` / `resolve_citation`.

SQLite owns source occurrences separately even when text blobs deduplicate. Workspace
and artifact locators establish durable identities across sessions; unknown identity
stays unassigned. Episodes close on context boundaries and bound extraction evidence.
The worker limits its queue and retries, checks policy revision at commit, and preserves
unprocessed coverage. Models cannot execute commands or choose endpoints.

Claims distinguish observations, suggestions, tasks and decisions. Supported explicit
claims require actual source quotes; reasons must also occur in source evidence.
Task completion/reopening and user corrections preserve history. Contradiction edges
remain separate from original claims. Browser project membership requires supported
references; retrieval checks supporting evidence against the caller’s scope.

Deletion removes owned evidence, recomputes support, invalidates queued/running work,
and blocks deleted source replay. Existing session-deletion recovery invokes this
cleanup when a semantic database exists. Retention accounts for SQLite side files,
prunes unpinned sources and pauses under unreclaimable pressure. Logical deletion is
not a claim of forensic erasure from SSDs/backups.

## What to test

From the feature worktree, using the main repository’s virtual environment:

```bash
../../.venv/bin/python -m unittest discover -s tests -v
../../.venv/bin/python -m unittest discover -s tests -p 'test_semantic*.py' -v
```

Verification: all 144 tests pass, including 34 semantic tests; syntax compilation
and `git diff --check` pass. The native full-suite run required macOS framework access.

Tests use synthetic envelopes and temporary databases. They do not start global
keyboard monitoring, screenshots, microphone capture or hosted inference. The suite
covers identity/replay, permission rejection, evidence ownership, episodes, malformed
extraction, stale commits, explicit claim grounding, task history, scoped retrieval,
deleted derived content and deletion recovery.

For offline model evaluation, see `docs/benchmarks/project-memory/candidates.md`,
`scripts/evaluate_project_memory.py --help`, and the checked-in result files. Runtime
configuration requires locally cached approved manifests/weights and the isolated
Ollama endpoint at `127.0.0.1:11455`. Normal tracker startup never starts or pulls a model.
Downloaded weights remain ignored under the worktree’s `data/model-cache`.

## Actual evaluation and limits

Mac14,9 / M2 Pro / 32 GiB; Ollama 0.33.3; Qwen2.5 Q4_K_M 0.5B and 1.5B.
The fixed synthetic corpus contains 16 development and eight held-out cases. Prompt
and schema were adjusted only on development data, then frozen for held-out runs.
Each held-out run records 32 timings; quality denominators remain eight unique cases.

| Held-out result | 0.5B | 1.5B |
| --- | ---: | ---: |
| Candidate type precision | 12.5% | 37.5% |
| Candidate type recall | 16.7% | 50% |
| Supported association precision | 100% | 100% |
| Artifact recall | 83.3% | 83.3% |

Association results largely reflect deterministic workspace anchors. They do not
prove meaningful semantic understanding. Candidate-type scoring does not verify
propositions, reasons or zero forbidden-source leakage; `unsupported_assertions` in
archived metrics counts misclassified decision candidates, not supported assertions.
Reports explicitly leave acceptance incomplete and selection false. Neither model is
enabled. Recorded RAM is an estimate from sampled process-tree RSS / Ollama model
memory, not a complete power or Metal peak measurement. Energy remains unmeasured.

Independent review found and fixed: private-derived claim survival after deletion,
unrelated decision promotion, excessive pruning under pressure, and project membership
leaking across caller scopes. Regression tests preserve those cases.

## Remaining implementation and acceptance work

1. Add proposition/reason/citation/status scoring and adversarial deletion/revocation
   evaluation. Improve local extraction on development data; use fresh held-out cases
   if tuning follows inspection of this held-out set. Keep all acceptance gates explicit.
2. Complete FTS-based candidate selection and independent-episode corroboration;
   current selection uses recent anchors and browser promotion uses explicit references.
3. Enforce the total semantic budget across every writer, make retention scheduling
   operational, and validate concurrent quota pressure. Current ingestion checks and
   explicit retention calls are not a complete automatic quota lifecycle.
4. Harden lifecycle coverage: generic extractor timeouts/failure classes, cancellation
   of in-flight native work, manual/automatic task-event ordering, and restart boundaries.
5. Measure enabled-worker versus baseline RAM/CPU and actual power over representative
   longer sessions. Isolated idle-service measurements alone are insufficient.
6. Build permission-checked authoritative VS Code/browser source adapters and foreground
   isolation. Then expose scoped read-only project context through MCP and validate an
   agent resuming a real project. Agent access must not grant wider capture permissions.

Keep this increment isolated from main until the remaining acceptance work is reviewed.
