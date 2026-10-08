# Semantic project memory — current implementation status

Updated 2026-10-08. Branch `feat/semantic-project-memory`; isolated worktree
`.worktrees/semantic-project-memory`. The [handover](handover-2026-10-08.md)
is the current continuation guide; [context](../context.md) includes live checkpoints.

## Implemented path

Approved VS Code visible excerpts / intentional notes → private native-window-bound
bridge → permission-checked SQLite evidence → bounded episodes → local extraction
→ validated source-backed claims/relationships → scoped project recall and citations.
Normal Mac screenshot/input/dictation capture remains a separate process and store.

Canonical workspace/file identities survive sessions. Text blobs deduplicate while
source occurrences retain timestamps and provenance. Claims distinguish observations,
suggestions, decisions and tasks; reasons must occur in supporting evidence.
Corrections, explicit task transitions, contradiction/support relationships, deletion
and scope-aware retrieval exist in the core; not all are exercised by the live adapter.

The opt-in pilot enforces private files, fresh ordered messages, strict native focus,
canonical approved roots, excluded paths, bounded evidence/queues, stale-commit barriers,
scheduled retention and SQLite page caps. One extraction job runs at a time. Focus-only
cancellation may retry twice after verification returns; pause/access cancellation does
not automatically retry. Explicit retry_notes recovers authorized cancelled notes.
Short single-line intentional TODO notes use deterministic exact-quote task parsing;
observed document TODOs receive no such promotion. See the [runbook](live-semantic-pilot.md).

## Verification and acceptance

After merging Aditya's main through e5cd6ed: **251 Python tests (92 semantic) and
6 Node tests pass**. Native full-suite execution requires macOS framework access.
Tests use temporary data, mocked input events and generated OCR images, not a live
microphone or global input tap. One upstream test emitted an unclosed-image ResourceWarning;
the suite passed.

Real one-project pilot validated native registration, approved visible-source storage,
stable-view dedup, reconnect/resumed intake, saved .env canary exclusion, intentional-note
acknowledgement, recovery and cited recall. Retained user notes yielded a supported
SQLite decision with its exact reason and a supported open restart-recovery task.
This proves the tested pipeline, not general semantic understanding. Some duplicate
jobs exhausted bounded retries and remain visibly cancelled; coverage reports omissions.

## Model acceptance and remaining work

Inference is local-only against an explicitly running cloud-disabled Ollama service.
No model downloads/service startup/default model inference occur in normal capture.
V2.4 reviewed heldout precision/recall: Qwen2.5 0.5B 67%/40%, Qwen2.5 1.5B 83%/100%,
Qwen3 1.7B 71%/100%. No configuration passed precision acceptance. See the
[benchmark index](benchmarks/project-memory/README.md) for actual evidence and limits.
The v2.5 intentional-TODO adapter change needs fresh general-quality evaluation;
one live note test does not replace it.

Next: representative resource baseline; fresh semantic/privacy evaluation and source
quality; broader native lifecycle/multiple-project checks; permissioned browser adapters;
scoped read-only MCP and a real agent project-resume test. Rich automatic cross-artifact
relationships remain incomplete; switching patterns alone are not proof of association.
No MCP service, graph UI or agent integration exists yet. Storage is local plaintext.

Aditya's normal-tracker context export is a separate rule-based distillation for AI use,
not the semantic SQLite graph. His lighter-capture, consolidated-memory and interactive
CLI changes are integrated on this branch without replacing the semantic pilot.
