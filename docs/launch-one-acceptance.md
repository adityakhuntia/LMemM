# Launch 1 acceptance record

Implementation qualification in progress, October 21, 2026. This is a local
early-access candidate, not approval for public distribution.

## Verified so far

- 916 isolated Python tests pass; 14 combined browser/editor extension tests pass.
- Existing project upgrade preserves IDs, evidence, task state and citations;
  interrupted migration rolls back. Optional folders keep stable ownership.
- Intentional notes/excerpts and browser snapshots have separate provenance.
  Supported tasks/decisions, explicit URL/file references and related-source
  navigation reuse the evidence lifecycle. Old AI scopes do not gain new origins.
- Resume, context copy and source navigation have backend/controller coverage.
  Seventeen synthetic native states rendered; Resume and browser evidence screens
  inspected. New-source and first-project-load refresh regressions fixed.
- Real Chrome for Testing with an isolated profile: native Control+Shift+S saved
  exactly the highlighted sentence. Page capture excluded synthetic password,
  textarea and hidden markers. Move/Undo affected the exact snapshot. Save toast
  with project name, Undo and Change project inspected.
- Standalone build and strict ad hoc signature verification passed. A copied app
  outside the checkout, under a path with spaces and minimal PATH, passed bundled
  service/citations, browser host, semantic MiniLM indexing/search, official MCP
  SDK three-tool handshake/context, permission probe and owned-service shutdown.
  AnyIO dynamic-backend packaging failure was reproduced and fixed.

Standalone verifier: `scripts/verify_standalone_memory.py --app dist/LMemM.app
--output REPORT.json [--model-cache PATH]`. Uses synthetic evidence and a copied
model cache; no personal text or hosted AI. Native renderer:
`scripts/memory_ui_smoke.py --output OUTPUT_DIRECTORY`.

Native screenshots: `/tmp/lmemm-launch-one-ui`. Real browser artifacts:
`/tmp/lmemm-launch-one-browser/artifacts/page-save.png`. These local temporary
artifacts are not a recording of the user's desktop or a published demo.

## Required before widening release

- Independent final code review and fixes, followed by final suite/build rerun.
- Developer ID/hardened runtime/notarization/stapling and fresh Gatekeeper test.
  Current default signature is ad hoc. Credentials have not been supplied.
- Observed second-Mac onboarding, browser installation and first useful save.
- Original physical crash sequence, real sleep/lock/recovery, and measured
  sustained resource workload with normal capture enabled. Unit/native fixture
  checks do not replace these hardware acceptance checks.
- Pilot with two developers and two knowledge workers: five-minute first save,
  two-minute resume after interruption and repeat use on another day. No users
  have been contacted and no pilot results are claimed.

Scope limits: Chrome/Chromium explicit text saving; no Safari connector, passive
history capture, graph explorer, broad inferred dependencies, store listing or
mandatory hosted AI. A source URL is attribution; retained snapshots are not
proof that a current live page still contains that text.
