# Local evidence embeddings — development selection

Selected for integration: `all-minilm:22m`, Ollama-local, 384-dimensional normalized
float32 output, 512-token limit, symmetric text inputs (no query/document prefix).
Manifest SHA-256: `1b226e2802dbb772b5fc32a58f103ca1804ef7501331012de126ab22f67475ef`.
Chunk version 1 retains <=1024-byte chunks with <=128-byte overlap. Runtime explicitly
sets `truncate:false`: token overflow fails visibly instead of indexing shortened text.
The retained source remains keyword-searchable when embedding fails.

| Candidate | Local layers | Dev hybrid Recall@5 | Dev paraphrase hybrid / keyword | Warm query embedding p95 |
|---|---:|---:|---:|---:|
| all-minilm:22m | 45,960,589 bytes | 19/20 (95%) | 9/10 / 5/10 | 11.5 ms |
| all-minilm:33m | 67,319,501 bytes | 19/20 (95%) | 9/10 / 5/10 | 14.8 ms |

Both vector-only runs reached 20/20 Recall@5; hybrid exact questions reached 10/10,
versus keyword 8/10. The smaller model has a credible development path to the approved
retrieval gates. This is a small synthetic development comparison, not production
quality or held-out acceptance. No held-out query scoring was run during selection.
Per-query scores and fixture hashes are in `development-22m.json` and
`development-33m.json`. A malformed non-zero-padded corpus date was corrected and
corpus hashes refrozen before the first successful scoring run; no model score
informed that repair.

Environment: target Mac, Ollama 0.33.3, isolated loopback port 11455, `OLLAMA_NO_CLOUD=1`,
one worker, one loaded model, dedicated ignored `data/embedding-models` cache.
The registry supplies Apache-2.0 license layers for both candidates. Installation was
explicitly approved; ordinary library import/startup performs no download. Runtime
checks every installed layer hash and the local manifest digest. No hosted fallback,
redirect or caller-provided endpoint exists.

Only query-embedding latency and downloaded asset size were measured here. The
10,000-chunk search p95, enabled-versus-baseline CPU/RSS, cold start, energy and
30-minute workload remain acceptance work; these numbers do not establish those gates.

Primary runtime/model references consulted during implementation:
[Ollama all-minilm](https://ollama.com/library/all-minilm),
[Ollama embedding API types](https://github.com/ollama/ollama/blob/main/api/types.go),
[Ollama embeddings documentation](https://github.com/ollama/ollama/blob/main/docs/capabilities/embeddings.mdx).
