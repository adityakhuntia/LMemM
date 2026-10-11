# Hybrid MVP baseline — 2026-10-10

Branch begins at `8ae1d6e`. No hybrid product code exists at baseline.

- Self-accessibility: four regressions pass using the existing guard from `11f5f3e`.
- Process inventory: no LMemM tracker/service running. Therefore no running-tracker
  CPU/RSS measurement is claimed.
- Synthetic corpus: 42 labelled queries across two canonical roots and two sessions;
  21 held-out queries, including 10 paraphrases and one no-evidence question. Corpus
  contains same-basename workspaces, exact identifiers, explicit notes, an older
  snapshot excluded by time bounds, and an unrelated page that is never ingested.
- Corpus and split SHA-256 digests are frozen in
  `tests/fixtures/project_memory/retrieval-v1/manifest.json` before model selection.
- The native crash sequence, lock/sleep recovery, baseline resource measurements,
  and real user-workload acceptance remain pending. Unit tests cannot prove them.

The first sandboxed suite stopped without a unittest summary at a native-framework
boundary. The framework-enabled rerun passed 693 tests in 8.860 seconds; the first
run is not counted as a pass. Raw outputs remain in the ignored per-plan workspace.
