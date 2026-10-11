# Local model benchmark candidates

Target: Apple M2 Pro, Mac14,9, 32 GiB system RAM; Ollama 0.33.3.
Isolated benchmark listener: 127.0.0.1:11455, OLLAMA_NO_CLOUD=1,
one loaded model and one inference. Only synthetic fixtures supplied.

Shortlist recorded before downloads/evaluation:

| Candidate | Quantization | Download size | Licence | Registry digest prefix |
| --- | --- | --- | --- | --- |
| qwen2.5:0.5b | Q4_K_M | 398 MB | Apache 2.0 | a8b0c5157701 |
| qwen2.5:1.5b | Q4_K_M | 986 MB | Apache 2.0 | 65ec06548149 |

Both use a bounded 8192-token context configuration and temperature zero.
Installed manifests/weight hashes and measured results will be recorded by the
benchmark. Download size is not resident RAM. No model selected for live use.

Primary references: [0.5B model](https://ollama.com/library/qwen2.5:0.5b),
[1.5B model](https://ollama.com/library/qwen2.5:1.5b),
[Ollama cloud-disable and residency settings](https://docs.ollama.com/faq).

Ruling: use an isolated local Ollama service, already installed, rather than
install a second inference runtime. No configurable remote endpoint, redirects
or automatic pulls during extraction. Local model manifest is required before
inference. The service is started explicitly for evaluation and stopped afterward.

## Continuation shortlist — before v2.2 held-out execution

Add Qwen3 1.7B Q4_K_M (about1.4GB weights), Apache-2.0. Keep the existing
8Ki-token context and3GiB runtime budget; measure rather than assume fit.
Disable thinking for bounded structured extraction; no cloud model alias.
Official cards: https://ollama.com/library/qwen3:1.7b and
https://huggingface.co/Qwen/Qwen3-1.7B . API setting:
https://docs.ollama.com/api/generate . The small Qwen2.5 candidates still
miss assertion gates on development; compare this candidate without
inspecting v2 held-out model results or widening budgets.
