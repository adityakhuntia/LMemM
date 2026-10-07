# Local semantic extraction benchmarks

Current result: **no selected model; automatic semantic inference remains disabled**.
All inputs are synthetic. No captured desktop, keyboard, microphone or personal
content is used by these runs. All inference used an isolated cloud-disabled
Ollama 0.33.3 service on 127.0.0.1:11455, with cached weights and thinking disabled.

## Read these records in order

- [Approved design](../../specs/2026-10-07-automatic-project-memory-design.md)
  defines the on-device scope and original quality/resource targets.
- [Candidate shortlist](candidates.md) records model cards and the extra Qwen3
  comparison before fresh heldout execution. Weights stay ignored in `data/`.
- `results/` contains the original v1 classification benchmark. Its type scores
  are not factual-accuracy acceptance.
- `v2/`, `v2.1/`, `v2.2/`, `v2.3/` contain development-only experiments and failures.
- [Frozen v2.4 configuration](v2.4/freeze.json) records prompt/corpus hashes.
  `v2.4/` has pre-review records; heldout files are explicitly audit1.
- **[Reviewed v2.4 results](v2.4-reviewed/)** are authoritative for this increment.
  These use audit2, the same frozen prompt, models and labels. They repeat the same
  heldout split after validation/audit repairs, not a new independent holdout.

## What is measured

The v2 corpus has 16 development and 8 fresh heldout episodes. The heldout episodes
contain five gold claims (observation, explicit choice, task, suggestion and a
choice with unknown reason), one project reference and two unrelated/hostile pages.
Gold labels are exact source quotes, reasons and task states. There is no semantic
judge model. This is a deliberately small controlled benchmark, not accuracy over
real sessions, paraphrases, long OCR or all project relationships.

`assertion_metrics` scores actual stored supported/user-asserted claims. Every
claimed citation must independently ground the quote and reason. Wrong statements,
reasons, states and duplicate claims are false positives; tentative claims do not
become supported assertions. `metrics` separately retains candidate-type scores;
do not confuse those with assertion accuracy.

Privacy audit2 exercises caller-scope exclusion, denied/private/unknown intake,
a private decision/reason with partial public support followed by browser revocation,
all-source deletion and citation resolution. It scans whole returned packets for
private canaries, not just citation IDs. All three reviewed runs reported **zero
leaks in 13 probes**, zero unsupported supported decision/completion assertions,
and zero invalid citation/grounding counts. Those bounded checks are not proof
that every future adapter or agent access path is privacy-safe.

## Reviewed heldout results — M2 Pro / 32 GiB

| Model | TP / FP / FN | Assertion precision | Recall | Estimated runtime peak | p95 (32 timings) |
| --- | --- | ---: | ---: | ---: | ---: |
| [qwen2.5:0.5b](v2.4-reviewed/qwen2.5-0.5b-heldout.json) | 2 / 1 / 3 | 66.7% | 40% | 0.64 GiB | 0.26s |
| [qwen2.5:1.5b](v2.4-reviewed/qwen2.5-1.5b-heldout.json) | 5 / 1 / 0 | 83.3% | 100% | 1.29 GiB | 0.33s |
| [qwen3:1.7b](v2.4-reviewed/qwen3-1.7b-heldout.json) | 5 / 2 / 0 | 71.4% | 100% | 2.29 GiB | 0.36s |

No candidate meets the conservative 95% assertion-precision target. The two larger
candidates recovered all five gold claims, but also misclassified reference content.
Supported-association precision was 100% and total artifact recall 83.3%; authoritative
workspace anchors dominate those metrics. They are not evidence of automatic semantic
browser grouping. [Raw rows](v2.4-reviewed/qwen2.5-1.5b-heldout.json) show the errors.

The95% assertion-precision and 80% claim-recall checks are additional conservative
execution rulings: an extractor that emits few or incorrect observations cannot
pass merely because deterministic workspace membership is accurate. Original
association/unsupported-decision/privacy gates remain in force.

RAM estimates take the larger of sampled process-tree RSS and Ollama reported model
memory; Metal/shared-memory accounting is incomplete. Timings repeat short synthetic
requests on a warm runtime, not 16 KiB mixed work. Enabled-worker versus baseline
RAM/idle CPU and actual power remain unmeasured. Resource/selection gates stay false.
The earlier idle result measures an unloaded service only. No budget was widened.

## Reproduce

From the feature worktree, first run tests:

```bash
../../.venv/bin/python -m unittest discover -s tests -v
```

For local benchmarks, start your isolated service with `OLLAMA_NO_CLOUD=1`,
`OLLAMA_HOST=127.0.0.1:11455`, one parallel worker and one loaded model, and a dedicated
ignored `OLLAMA_MODELS` cache. Download a shortlisted model explicitly; the benchmark
never downloads weights or starts a service. Keep the existing Ollama instance alone.

Create an ignored runtime JSON with `executable`, `model_path` (local manifest file),
and `context_limit: 8192`. Accepted manifests are Qwen2.5 0.5B/1.5B and Qwen3 1.7B.
Paths are machine-specific; the checked-in reports contain hashes, not a portable
weight package. Then:

```bash
../../.venv/bin/python scripts/evaluate_project_memory.py \
  --manifest tests/fixtures/project_memory/assertions-v2.json \
  --runtime-config data/runtime-1.5b.json --split development \
  --output data/benchmark-reproduction
```

Evaluate heldout only after freezing prompt/configuration/scoring, with
`--split heldout --timing-repeats 4`.
Do not tune using these heldout outputs and then present them as independent
acceptance. Future model/prompt work needs a new heldout split. Stop only your
owned benchmark service when finished.
