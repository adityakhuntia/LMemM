# Hybrid Memory implementation review and decisions — 2026-10-11

Independent read-only whole-implementation review (gpt-6-astra, `8ae1d6e..0678695`) reproduced ten material findings. All entered one regression/fix pass; no second review was dispatched. The provenance presentation finding was regraded Important because users must distinguish observed evidence from their own assertions.

All fixes are on local main. Final verification: **807 Python tests**, **6 Node bridge tests**, and seven real AppKit synthetic window states. No launch acceptance is implied. No personal sources were enrolled or transmitted by these checks. The earlier hosted Codex test used only two synthetic notes.

## Findings addressed

| Finding | Fix and verification |
|---|---|
| Capture after pause/revoke | Atomic pause, active-binding and revision validation at commit; regression asserts no source/chunk/job/ack |
| Paused note reconciliation acknowledged prematurely | Pending work keeps journal/fence until resume successfully applies saved authority |
| Reader recreates consumed note fence | Journal observation/fencing and consumption serialized with consistent lock order |
| Deleted notes return after re-enrollment | Saved-authority reconciliation fenced before reactivated project can expose notes |
| Agent state crosses projects or disappears after restart | Owner-only persisted connection inventory, project-specific selection/revocation, delayed connection/enrollment tests |
| Interrupted model upgrade mixes manifest and generation | Startup reconciles durable desired manifest; tests inject failure before/after generation creation and drain new jobs |
| Service failure cannot retry | Refresh explicitly retries; child exit invalidates state; response generations reject obsolete completions |
| Revoked grants exhaust lifetime connection quota | Retire revoked capabilities/configs; bound eight active grants; test ten connect/revoke cycles and restart inventory |
| Enrollment 65 corrupts startup | Bound before insertion, serialized enrollment; legacy excess bindings disabled rather than deleted |
| Default MCP search silently widens time | Default two-day interval and explicit effective start/end; All retained remains an explicit UI selection |
| Provenance/truncation hidden | Observed content/Your note labels, truncation notices and enrollment/index/pending status; synthetic native screenshots refreshed |

## Execution decisions (complete ledger rulings)

- continue backend work while live stability/workload acceptance remains pending — automated backend work cannot exercise a user's physical lock/sleep workflow; native UI integration still requires actual acceptance — cost if wrong: backend progress cannot establish launch readiness.
- repair non-zero-padded synthetic date 2026-10-9 before any model/query scoring and refreeze corpus — ISO validation correctly rejected malformed fixture; no retrieval results or held-out labels informed the repair — cost if wrong: fixture hashes differ from baseline commit, explicitly recorded.
- durable private native-note journal fences reads without blocking on IPC acknowledgment; a cross-process file lock serializes authority saves and reconciliation — native JSON remains authoritative and UI never waits on model work — cost if wrong: stale cross-store claims.
- live physical/native paired 30-minute workload and three external tester observations remain pending, not fabricated — automation provides synthetic performance/UI/protocol evidence, not human workflow acceptance — cost if wrong: implementation cannot be described as launch-approved.
- recover legacy excessive enrollment by disabling bindings beyond the first 64 in stable UI-ID order, retaining every binding for inspection — prior code could persist an unstartable 65-binding database; fail closed rather than discard evidence — cost if wrong: an excess project requires explicit re-enrollment after freeing a slot.
- physical foreground-switch abort and sleep/lock behavior remain unaccepted — automated lifecycle tests cannot substitute for the original native workflow — cost if wrong: an undetected native abort remains possible.
- paired 30-minute app/runtime resource acceptance remains pending — the synthetic search probe measures a narrower process/workload — cost if wrong: real runtime memory or energy overhead may exceed budget.
- real extension installation/enrollment and three consented external testers remain pending — no live user/tester observations were performed or invented — cost if wrong: installation and usability problems remain undiscovered.
- retain the recorded real local-model/search evidence without a new download or performance run in this fix pass — ranking/model assets are unchanged, and crash recovery has synthetic manifest/dimension regression coverage — cost if wrong: actual runtime setup regressions could escape those tests.
- experimental generative extraction and browser intake stay outside enabled MVP scope — the approved feature uses local-file evidence and deterministic explicit-note claims — cost if wrong: users expecting those excluded capabilities will not receive them.

No deferred minor findings. Physical/native and external acceptance remains pending as described in [acceptance](acceptance.md). Frozen retrieval ranking, model selection and held-out labels were not retuned during the fix pass.

The final suite ran outside the sandbox because AppKit/private socket checks require it. A sandboxed suite process aborted; this is not evidence that the original live tracker shutdown is fixed or reproduced. Existing ResourceWarnings are emitted by older test file reads; the completed full suite exits successfully.
