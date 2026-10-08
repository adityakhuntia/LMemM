# Claude handover — LMemM semantic project memory

Updated 2026-10-08. Read this first, then [the detailed handover](docs/handover-2026-10-08.md),
[context.md](context.md) and [the live runbook](docs/live-semantic-pilot.md).

## Branch and integration

Continue on `feat/semantic-project-memory`. All current Aditya main commits through
`e5cd6ed` are included, merged in `b369359`. The feature was published through `1f26e25`
before this entry-point document. Main has not been changed by this publication.
Do not assume the feature is merged into main or start a parallel replacement branch.

Aditya's additions retained: lighter screenshot/OCR/storage behavior, capture-cost docs,
rule-based AI context export, schema-3 consolidated memory and the interactive CLI menu.
The native floating Left/Plan widget remains in the normal tracker. It is not launched
by the semantic pilot, and semantic tasks are not wired into that widget.

## What Divyaansh built

An isolated local semantic evidence store and experimental VS Code source adapter:

Approved visible local file excerpts / intentional notes → private native-window-bound
bridge → SQLite evidence → bounded episodes → local model selection and validation →
source-backed claims/relationships → scoped project recall with citations.

Canonical workspace/file paths anchor projects/artifacts across sessions. Evidence
text deduplicates without losing occurrence/provenance. Core supports decisions,
reasons, observations, suggestions, tasks, corrections, relationships, scoped retrieval,
retention and dependent-source deletion. Some core capabilities are only fixture-tested,
not fully exercised by the live adapter.

Live debugging repaired native focus fallback, grant revision publication, publisher
leases/re-registration, note acknowledgement and stable retry identity, silent note-command
failures, orphaned episode scheduling and focus-cancelled inference recovery. Focus-only
jobs retry at most twice; pause/access cancellation does not automatically retry. Explicit
`retry_notes` waits for verified focus and is cleared by pause. Unknown secure-field states
still fail closed. Single-line intentional `TODO:` notes use deterministic exact-quote
classification; TODOs seen in documents are not promoted.

## Evidence and honest status

After the main merge: **251 Python tests (92 semantic) and 6 Node tests passed**.
Native full-suite execution needs macOS framework access. An upstream thumbnail test
emitted an unclosed-image ResourceWarning but did not fail. The new entry-point document
is documentation only.

Live one-project checks passed registration, approved visible-source capture/storage,
stable-view dedup, reconnect/resume, a saved .env canary exclusion, intentional-note
acknowledgement, bounded recovery and cited recall. Recall returned:

- Decision: `We chose SQLite because memory should stay local.`
- Exact reason: `memory should stay local.`
- Supported open task: `TODO: Test Restart Recovery`

Both claims resolve to exact retained user_note sources. Duplicate-note jobs that exhausted
retries remain visibly cancelled. Coverage reports truncation/unprocessed evidence.
This is a small demonstrated pipeline, not general semantic acceptance.

No local model has passed the overall precision gate. Reviewed v2.4 Qwen2.5 1.5B
precision/recall was 83%/100%; adapter v2.5 requires fresh evaluation. MCP, browser
semantic adapters, graph UI and real AI-agent project resume are not implemented.
Normal screenshot/input capture is still separate from semantic intake.

## Relevant code and storage

- `semantic_memory/`: store, episodes, worker, local runtime, claims/relationships,
  scope-aware recall, retention/deletion and native live bridge.
- `extensions/lmemm-source/`: opt-in VS Code publisher and intentional-note commands.
- `scripts/live_project_memory.py`: collector, status/control and read-only recall.
- `context.py`: Aditya's separate rule-based export from normal tracker memory.
- `widget.py`: normal-tracker floating Left/Plan UI.
- Normal store: schema-3 `data/memory/memory.json`, sessions and requested context exports.
- Pilot store: private configured data directory containing SQLite, bridge and controls.

Model weights, runtime configuration, bridge grants/tokens, captured evidence and local
.env test data are not committed. Do not add those to Git or request their contents in logs.
Storage is local plaintext; no hosted inference fallback. The pilot never starts/downloads
models. The normal tracker does not enable semantic inference automatically.

## Test and run

In a normal feature checkout with dependencies installed:

```bash
python -m unittest discover -s tests
node --test extensions/lmemm-source/bridge.test.js
python lmemm.py           # interactive menu
python lmemm.py start     # normal tracker and widget
```

In Divyaansh's existing worktree use `../../.venv/bin/python` instead of `python`.
Follow the live runbook for cached local model config, cloud-disabled Ollama service,
collector startup, VS Code development-host launch and grant connection. No secrets or
model assets are in this repo. After lock/sleep, explicitly resume the collector; reconnect
the extension if needed. Do not repeatedly resubmit notes to work around cancelled jobs.

## Next work, in order

1. Broader lifecycle/multiple-project acceptance and representative CPU/RAM/power baseline.
2. Fresh semantic/privacy evaluation, better precision and corroborated relationships.
3. Permissioned browser source adapters and website-level controls.
4. Scoped read-only MCP exposing project context/citations; test an agent resuming a real
   project. Agent access must not widen capture scope; keep tentative claims/coverage visible.
5. Improve automatic relationships and optimize based on measured workloads. Hosted inference
   and broad graph UI are later discussions.

Before merging this feature to main, review the detailed handover's acceptance limits.
Do not mark general model accuracy or the complete AI-agent MVP done based on the note test.
