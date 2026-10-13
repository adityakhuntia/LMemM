# Hybrid Memory acceptance — 2026-10-10

Device: Apple M2 Pro, 32 GiB RAM, macOS 27.0.

Status: implementation independently reviewed and material findings fixed; **not launch-approved**. Mandatory live/external observations remain pending. No personal evidence was enrolled for these tests.

| Check | Observed result | Limit |
|---|---|---|
| Production held-out hybrid Recall@5 | 100%, 20 answerable queries | Small frozen synthetic corpus; not production effectiveness |
| Keyword held-out Recall@5 | 75%, same 20 queries | No semantic model |
| Held-out paraphrase Recall@5 | Hybrid 100% vs keyword 50%, 10 queries | Frozen before scoring; no retuning |
| Held-out exact Recall@5 | Both 100%, 10 queries | No exact regression on this set |
| Default assertion precision/recall | 8/8 emitted gold claims; 100% / 100% across 20 fresh cases | Explicit-note deterministic extraction only; experimental model-generated claims disabled |
| Unsupported claims/reasons/citations | 0 in fresh assertion probe | Not a guarantee for arbitrary phrasing |
| 10k authorized-chunk warm hybrid p95 | 0.251 s | Synthetic document vectors duplicated to isolate scoring; query embedding is real |
| Probe peak nonmodel RSS | 59,883,520 bytes | Absolute Python probe process, not additional paired app overhead |
| Probe 60-second idle CPU | Approximately 0.000072% of a core | Probe process only, not the runtime or complete native app |
| Probe semantic DB size | 35,676,160 bytes | 10k synthetic short sources |
| Hosted Codex resume | Passed with two synthetic notes; one MCP context call; both exact citations present | No personal evidence sent |
| SDK integration | Real stdio initialization/list/call/revocation tests pass | Socket capability backend; no handwritten MCP transport |
| Native pane | Real AppKit states and source/Overview captured | Synthetic native smoke; not original crash workflow |
| 30-minute paired native resource workload | **Pending** | No valid paired baseline/runtime RSS/energy/retained workload observation |
| Original shutdown sequence, physical sleep/lock | **Pending** | Automated self-AX and lifecycle regression tests pass; no physical acceptance claim |
| Three external consented testers | **Pending** | No testers contacted or fabricated |

Machine-readable evidence: [production development](production-development.json), [production held-out](production-held-out.json), [fresh assertions](assertions.json), [full search probe](full-search-probe.json). Native evidence and user steps are in the [runbook](../../../hybrid-memory-runbook.md).

The first attempted hosted synthetic Codex call correctly returned empty scope because the test fixture used a noncanonical macOS `/var` path while enrollment resolved `/private/var`. The harness now asserts the local packet contains the decision/task before invoking an external host. Its final successful result is recorded in [codex-resume.json](codex-resume.json).

Missing observations are not treated as passes. The acceptance harness rejects absent resource samples, unloaded-model claims, empty assertion output, unsupported statements/missing citations, exact-match regression and modified frozen fixture bytes.

Post-review verification (2026-10-11): 807 Python tests, 6 Node bridge tests and seven refreshed real AppKit synthetic states passed. Ten material findings and evidence trust presentation were fixed in one regression pass. See [review and decisions](review-and-decisions.md). The mandatory pending acceptance rows above remain pending.

## Live user smoke-test update — 2026-10-11

Subsequent user testing confirmed real VS Code capture, pause/resume without
reconnecting, project notes, semantic search, restart persistence, sleep/lock
recovery and Alpha/Beta isolation. A supplied Beta citation screenshot shows
retained note text, timestamp and the correct workspace path. Stability was
reported good so far. Thus sleep/lock and extension setup now have user-reported
manual evidence; the earlier pending row describes the original acceptance run.
Original crash-sequence reproduction, a measured paired 30-minute resource run
and three external testers are still pending. No full launch acceptance is claimed.
Latest regression suite: 815 Python tests and 6 Node extension tests pass.
See the updated [handover](../../../../handover.md) for a reproducible live demo.

2026-10-13 readiness remediation: cofounder setup improvements are integrated
locally with all five audit concerns resolved. Requirements installed into a
fresh Python 3.11 environment; all 839 Python tests and six extension tests pass.
Ten native synthetic UI states rendered, including settings and recovery.
[Refreshed held-out retrieval](readiness-held-out.json) remains hybrid 20/20
Recall@5 (exact 10/10, paraphrase 10/10), using the owned installed local model.
This does not replace fresh second-Mac permissions/setup or pending launch gates.
