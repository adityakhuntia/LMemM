# Launch One Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make returning to a project useful across notes, code and explicitly saved browser evidence.

**Architecture:** Extend the existing SQLite evidence/graph service with independent project ownership and intentional/browser sources. Reuse scoped retrieval for Resume and export, and connect a Manifest V3 extension through an authenticated native messaging host. Keep captured evidence and generated interpretation distinct.

**Tech Stack:** Python, SQLite/FTS, existing local embeddings, native AppKit UI, JavaScript Manifest V3 extension, macOS py2app.

**Spec:** `docs/superpowers/specs/2026-10-20-launch-one-design.md`

## Global Constraints

- Chrome/Chromium explicit saves only; no persistent all-sites access or background browsing history.
- No mandatory workspace or Codex; preserve existing workspace projects and citations.
- Pause/lock/disconnect failures have no hidden offline save queue.
- Saved browser text is untrusted evidence, not instructions or user commitments.
- Existing AI grants do not silently gain new source origins.
- Alias builds do not count as standalone release acceptance.
- Preserve private untracked `context.md`, personal data and unrelated work.
- Direct-to-main integration is authorized, after checking upstream and testing.

## Review Focus

- Concurrent saves/retries and project changes: one snapshot, correct owner, no stale scoped response.
- Missing/deleted destination or stopped app: no success acknowledgement and no silent fallback project.
- Long Unicode pages and hostile URLs: bounded text, accurate truncation, no script/file URL launch.
- Partial upgrades or permission failures: preserve original data and provide actionable recovery.
- Real installation without checkout/PATH: app, connector host and workers resolve bundled resources.

## Delivery structure

Tasks 1–3 produce the independently usable folder-free Resume slice. Tasks 4–5
add browser capture using that source contract. Tasks 6–7 qualify distribution.
Implement sequentially in this session; request one independent final review.
Do not recruit testers, publish a browser listing, or claim external acceptance.

### Task 1: Independent project identity and migration

**Files:** modify `semantic_memory/migrations.py`, `project_scope.py`,
`api_contracts.py`, `service.py`, `src/memory_notes.py`; add
`tests/test_memory_project_identity.py`.

**Interfaces:** `ProjectBinding.workspace_root: str | None`;
`bind_project(store, ui_project_id, root: str | None, at) -> ProjectBinding`;
`MemoryService.enroll(ui_project_id, root=None) -> dict`. New folder-free IDs
derive from stable UI identity, not project title. Existing IDs remain unchanged.
Keep optional workspace associations unique; attaching later does not re-ID.

- [ ] Add migration fixture tests asserting unchanged IDs/citation IDs/task state,
  two distinct folder-free projects, rename stability, unique optional roots,
  rejected ambiguous reassignment and rollback on a failed upgrade.
- [ ] Run `.venv/bin/python scripts/run_tests.py -p test_memory_project_identity.py -v`; confirm failures describe missing new behavior.
- [ ] Add atomic schema v3 migration with a verified pre-upgrade private backup;
  update version validation and binding consumers. Keep native-note lock order.
- [ ] Re-run focused tests, then existing enrollment/migration/note tests through the isolated runner.
- [ ] Commit only this slice: `feat: support project memory without a workspace`.

### Task 2: Explicit sources and evidence-backed relationships

**Files:** add `semantic_memory/intentional_sources.py`,
`tests/test_memory_intentional_sources.py`; modify `contracts.py`, `store.py`,
`policy.py`, `note_sync.py`, `relationships.py`, `retention.py`, `grants.py`,
`retrieval.py`, `search.py`, `context_service.py`, `service.py`, `api_contracts.py`.

**Interfaces:** `save_intentional(store, project_id, payload: dict) -> dict`
returns `{source_id, project_id, duplicate}`; payload has `request_id`, `kind`
(`native_note`, `pasted_excerpt`, `browser_selection`, `browser_page`), `text`,
`title`, optional `url`, and `truncated`. Service, not caller, assigns save time.
`move_saved_source(store, source_id, project_id) -> dict` is atomic;
`delete_saved_source(store, source_id) -> dict` deletes derived evidence.
Transport authorization remains the caller's responsibility; these functions
validate active project ownership again under the transaction lock.

- [ ] Add failing tests for note/excerpt provenance, idempotent replay, same key
  with changed payload rejection, HTTP(S)-only URLs, text byte limits/Unicode,
  source deletion cascades and moving ownership with outstanding read fences.
- [ ] Run isolated `test_memory_intentional_sources.py`; observe expected failure.
- [ ] Implement dedicated source provenance and project authority, replacing fake
  editor envelopes for new notes. Preserve old source/citation resolution through
  a compatibility adapter. Use existing chunk/index scheduling after durable save.
  Bound source text to 128 KiB UTF-8, title to 512 characters and URL to 8192
  characters; explicit truncation metadata, no silent misrepresentation.
- [ ] Test that only explicit user note intent or a user record-decision/task
  action creates supported commitments; hostile browser TODOs do not. Add
  same-project URL/file reference tests, rejection of guessed dependencies,
  relationship removal, reason grounding and recomputation after evidence removal.
- [ ] Implement `record_claim(store, project_id, source_id, kind, start, end,
  reason_span=None) -> dict` and `remove_relationship(store, project_id, edge_id)`;
  validate retained span offsets. Standardize relation direction via adapter
  rather than silently changing old stored edge meaning.
- [ ] Test old AI grants exclude new origins; add explicit scope selection on new
  grants. Run note, retention, relationship, search, context and grant regressions.
- [ ] Commit: `feat: retain intentional sources with supported project relationships`.

### Task 3: Resume, related sources and context copy

**Files:** add `semantic_memory/resume.py`, `src/resume_pane.py`,
`tests/test_memory_resume.py`; modify `service.py`, `src/memory_controller.py`,
`src/memory_view.py`, `src/memory_pane.py`, `src/window.py`,
`scripts/memory_ui_smoke.py` and relevant native UI tests.

**Interfaces:** `resume_project(store, ctx, project_id) -> dict` returns
`{project_id, saved_activity, decisions, open_tasks, related_sources, citations}`;
`export_project_context(store, ctx, project_id, max_chars=24000) -> str` reuses
authorized data and includes exact citation IDs, source provenance and omissions.
Add owner-authorized service methods; do not expand MCP methods implicitly.

- [ ] Write failing tests for empty and populated Resume, cross-project isolation,
  source-backed reasons, complete/reopen, removed references, revoked reads,
  deterministic bounded export and browser prompt-injection text quoted as data.
- [ ] Run isolated `test_memory_resume.py`; confirm expected missing behavior.
- [ ] Implement Resume data and export; authorize/recheck before serialization.
  Last activity is labelled saved activity, never inferred live behavior.
- [ ] Add Resume as first project tab; retain Overview/Memory. Add excerpt form,
  optional workspace setup, evidence/related-source links, explicit record task
  or decision actions and Copy context. Preserve optional AskCodex and its fences.
- [ ] Run focused UI/controller tests and render empty/populated Resume, source,
  folder-free setup, paused and error states with the native smoke script.
  Inspect screenshots; verify copy/paste against source IDs in a test project.
- [ ] Commit: `feat: resume projects from recorded decisions tasks and sources`.

### Task 4: Authenticated browser native host and pairing

**Files:** add `semantic_memory/browser_host.py`, `browser_pairing.py`,
`tests/test_memory_browser_host.py`, `packaging/browser_host_main.py`;
modify `service.py`, `ipc.py`, `src/memory_controller.py`, `src/memory_pane.py`.

**Interfaces:** paired connector protocol v1 supports `list_projects`, `save`,
`move`, `undo`, `status`; request `{version, request_id, method, params}`.
Response `{request_id, ok, result}` or `{request_id, ok:false, error:{code,message}}`.
Save/move/undo use Task 2 methods. Restrict move/undo to sources created by that
pairing; connector can never read arbitrary retained text or owner credentials.

- [ ] Check current official Chrome native messaging/security documentation
  before implementing host framing, allowed extension origins and installation.
- [ ] Add failing tests for unpaired/revoked callers, malformed frames, oversize
  input, unknown methods, app stopped/paused/locked, destination deleted, duplicate
  retry and revoked pairing during a pending save. No false Saved response.
- [ ] Run isolated `test_memory_browser_host.py`; confirm expected failures.
- [ ] Implement bounded length-prefixed native messaging and a private credential
  handshake bound to approved extension identity. Store pairing secret in private
  host/app files, not page-accessible script or source. Do not rely on the native
  host being impossible to invoke manually; threat boundary is the OS account.
- [ ] Implement native Settings pairing/disconnect/recovery and approved project
  listing. Acknowledge save only after durable commit; reject locked/paused saves.
- [ ] Verify frame/session errors cannot terminate the memory service; run host
  and existing service/IPC tests. Commit `feat: pair browser saves with project memory`.

### Task 5: One-action browser saves

**Files:** add `extensions/lmemm-browser/{manifest.json,background.js,capture.js,
popup.html,popup.js,bridge.js,bridge.test.js,capture.test.js,README.md}`;
add native install helper `scripts/install_browser_host.py`.

**Interfaces:** Task 4 protocol via `connectNative`; selection/context-menu,
configurable command and extension click call a common `saveCapture()` routine.
Extension stores destination ID/display name only, never a hidden page-text queue.

- [ ] Write Node tests for first-use chooser, selection shortcut/right-click,
  page fallback, stale project, visible-text extraction, Unicode bounds, ignored
  form/password fields, private/unsupported pages and retry without double save.
- [ ] Run `node --test extensions/lmemm-browser/*.test.js`; confirm missing behavior.
- [ ] Implement Manifest V3 activeTab/scripting/nativeMessaging/contextMenus/storage
  with no persistent host permissions. Use documented browser shortcut setup;
  validate capture support before execution and do not inject into private tabs.
- [ ] Add destination badge/title and accessible confirmation `Saved to [project]`
  with Undo/Change project. Keep confirmation reachable through extension UI if
  page overlays are unavailable; server-acknowledged move updates destination.
- [ ] Run Node tests and real Chrome flow with a disposable profile/project:
  first save, second one-action save, Undo, move, offline/error, restart/reconnect.
  Retain screenshots and exact evidence/citation comparisons in handover.
- [ ] Commit: `feat: save browser evidence with one action`.

### Task 6: Standalone runtime and connector installation

**Files:** modify `build_app.sh`, `setup.py`, `packaging/app_main.py`,
`semantic_memory/runtime_environment.py`, `src/config.py`, browser host installer;
add `tests/test_standalone_paths.py` and `docs/launch-one-installation.md`.

**Interfaces:** frozen workers resolve a bundled executable/resource entry point;
normal developer mode keeps existing venv behavior. User data belongs in a stable
per-user Application Support directory, with explicit legacy-data import rather
than silent reset. Browser manifest names installed app resources, not checkout.

- [ ] Add failing tests for frozen worker launch, no checkout/venv/PATH, spaces and
  Unicode in installed paths, missing resources, permission errors and legacy-data
  import interrupted before commit. Preserve source IDs and backup original data.
- [ ] Run isolated `test_standalone_paths.py`; confirm expected missing behavior.
- [ ] Implement packaging resources/dependencies, app/service/host worker modes,
  user data path and import recovery. Model install remains an explicit first-run
  action with clear progress/failure; keep keyword/notes use available as designed.
- [ ] Build standalone and install outside checkout; test workers, model, host,
  permissions and relaunch with development paths unavailable. Fail build on
  missing required resources; do not swallow signing failures as success.
- [ ] Document available signing state and external Apple credentials if blocked.
  Commit `build: package standalone project memory and browser host`.

### Task 7: End-to-end release qualification and handover

**Files:** update `handover.md`, `docs/current-context.md`,
`docs/launch-one-installation.md`; add `docs/launch-one-acceptance.md`.

- [ ] Run `./scripts/test.sh` and both extension Node suites; fix reproducible
  failures without reading/modifying personal app data. Record actual counts.
- [ ] Exercise the shared interrupted-project demo: note, browser source, decision,
  task, optional VS Code source, restart, historical citation, Resume and export.
  Test deletion/move/revocation across UI, search, graph and AI context.
- [ ] Render and inspect all new native states; run real browser integration,
  sustained resource session, original crash sequence and sleep/lock recovery.
- [ ] Request independent final code review, resolve findings and rerun affected
  checks. Record unavailable second-Mac or credential checks as release blockers.
- [ ] Document installation/demo steps, exact shipped value, limitations, evidence
  and next pilot. Never claim pilot or second-Mac results without observing them.
- [ ] Fetch origin/main; safely reconcile any new work, preserve `context.md`, run
  affected regressions and commit qualified delivery to main. Publish authorized
  commits only after verification; do not publish a store listing.

## Plan self-review

Spec coverage: Tasks 1–2 own identity, migration, sources and graph; Task 3 owns
Resume/export; Tasks 4–5 own capture/pairing and simple saving; Task 6 owns actual
installation; Task 7 owns release evidence. Review-focus failures have explicit
tests in Tasks 1–2, 4–6. No new public APIs bypass existing project authorization.
This is planned work, not a claim of implementation or launch readiness.
