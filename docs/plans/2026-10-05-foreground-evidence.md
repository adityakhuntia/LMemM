# Foreground Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save the verified foreground window and use consistent source coordinates throughout OCR, content extraction and activity analysis.

**Architecture:** A focused capture-geometry module owns native window selection, validation and coordinate projection. Tracker captures the selected window directly and rejects unstable context. Resolver and activity consume versioned geometry while retaining legacy display-frame behavior.

**Tech Stack:** Python, existing PyObjC ApplicationServices/AppKit, Pillow, local macOS screencapture, unittest.

**Spec:** [Approved foreground evidence design](../specs/2026-10-05-foreground-evidence-design.md)

## Global Constraints

- Match exactly one on-screen layer-zero window owned by the foreground PID; at most two points of edge discrepancy.
- Missing Accessibility permission permits only an explicitly labelled single-candidate fallback. AX errors and ambiguous geometry fail closed.
- Window capture uses `screencapture -x -o -a -t jpg -l WINDOW_ID PATH`; retain the 1280-pixel long-edge downscale.
- Support windows fully contained in one display; reject spanning/off-screen windows.
- New `capture.version = 2` metadata contains source bounds, selection method, display bounds, window ID and actual image dimensions; legacy frames are unchanged.
- Never read AX editable values or broaden input eligibility. Do not copy/enqueue rejected images.
- Keep processing local and preserve notes, provenance, deletion and input timing/linkage.

## Review Focus

- An app disappears while AX is queried: reject stale ownership (Task 1).
- Transparent/invalid auxiliary windows and duplicate geometry: no arbitrary selection (Task 1).
- JPEG dimensions disagree with point bounds after capture: reject before linking (Task 2).
- A browser becomes private without changing its window ID: discard the frame (Task 2).
- Same item survives a resize or capture-format change: do not classify reframing as typing (Task 3).

## Files and responsibilities

- Create `capture_geometry.py`: selection, native structural AX query, display containment, metadata mapping, comparison signature.
- Create `tests/test_capture_geometry.py`: pure/native-adapter fixture tests.
- Modify `tracker.py`: verified front-window selection, window-only capture lifecycle, diagnostics, pointer and activity integration.
- Modify `resolver.py`: shared versioned pointer projection and geometry validation.
- Modify `tests/test_memory_pipeline.py`; create `tests/test_window_capture.py`: lifecycle and integration regressions.
- Modify `tests/test_resolver.py` and relevant input pipeline fixtures only where capture behavior changes.
- Update README, HANDOVER, context and this plan with verified behavior and remaining live checks.

### Task 1: Verified window selection and source geometry

**Interfaces:**
- `focused_bounds(pid: int) -> tuple[str, dict | None]`: status `verified`, `permission_missing`, or a named error; read only AX focused window, owner, position and size.
- `select_window(windows: list[dict], pid: int, focus_status: str, bounds: dict | None) -> tuple[dict | None, str]`: validated CG candidate and method/error.
- `containing_display(bounds: dict, displays: list[dict]) -> tuple[int, dict] | None`: exactly one display fully contains source bounds; one-based index.
- `local_pointer(global_point: tuple[float, float], bounds: dict) -> dict | None`: window-local points or null.

- [ ] Write tests asserting a Safari auxiliary window loses to the AX match; a small dialog wins when focused; two candidates within the two-point tolerance reject; invalid/nonfinite bounds and stale AX owner reject; only missing permission plus exactly one valid candidate falls back. Assert other-PID/layer/transparent windows are ineligible.
- [ ] Run `.venv/bin/python -m unittest discover -s tests -p test_capture_geometry.py -v`; confirm failure before implementation.
- [ ] Implement the interfaces in `capture_geometry.py`, including AX return/error handling and window/display rectangle validation. Integrate selection into `tracker.front()` while keeping its existing keys and adding selection/skip status. Preserve app identity when no verified window is available so diagnostics and allowlist support can operate.
- [ ] Add display/pointer tests: a display left/above primary, containment at boundaries, straddling/partial-offscreen rejection, pointer inside and outside. Run focused geometry and existing input-monitor tests; confirm pass.
- [ ] Commit verified selection and geometry helpers with tests.

### Task 2: Window-only capture with stable context

**Interfaces:**
- `tracker.screenshot(path: str, window_id: int) -> bool`: window-only command, successful downscale and valid image required; failure removes output.
- `capture_metadata(window: dict, display: dict, image_size: tuple[int, int]) -> dict`: version-2 capture block; validate source/image aspect ratio within pixel-rounding tolerance.
- `tracker.Tracker.capture(trigger, pinned=False)` retains existing return type and queue contract.

- [ ] Write capture tests asserting exact `-l`, `-o`, `-a` arguments and absence of `-D`/display capture. Test command failure, missing/corrupt image and aspect mismatch; all must leave no queued frame or input source copy.
- [ ] Run `.venv/bin/python -m unittest discover -s tests -p test_window_capture.py -v`; confirm the existing capture implementation fails the new assertions.
- [ ] Implement window-only screenshots and point/display metadata; `screen.w/h` becomes source dimensions only for version 2, `window_region` becomes `[0,0,1,1]`, and sampled pointer becomes source-local. Validate actual JPEG dimensions before metadata publication.
- [ ] Write normal-timer and note-trigger tests for missing/changed foreground, bounds, title, URL, tab title and private state. Assert discard/retrigger and no evidence linkage for rejected captures. Use real synthetic JPEGs in fixtures, replacing placeholder `b'image'` mocks.
- [ ] Generalize post-capture validation to every trigger. Add named skip counters and rate-limited terminal diagnostics for ambiguous focus and unsupported geometry; preserve existing sensitive-context/pause checks.
- [ ] Run focused capture, memory-pipeline, dictation-integration and input-pipeline suites; confirm pass and commit this task.

### Task 3: Shared mapping and comparison boundaries

**Interfaces:**
- `pixel_scales(meta: dict, image_size: dict) -> tuple[float, float]`: validated per-axis mapping; legacy uses existing display dimensions, malformed version 2 raises `ValueError`.
- `project_pointer(meta: dict, image_size: dict, key: str) -> tuple[float, float] | None`: projects source-local `pointer` or legacy `cursor`.
- `comparison_signature(meta: dict, image_size: dict) -> tuple`: app/window/URL plus source version/mode/bounds and actual dimensions.

- [ ] Write tests for legacy projection, version-2 x/y scaling, negative global origins with local points, and missing/malformed version-2 geometry. Assert independent axis scales and explicit invalid-geometry failure.
- [ ] Run geometry/resolver tests; confirm missing shared helpers or old assumptions fail.
- [ ] Implement mapping/signature helpers; use them in `resolver.resolve`, `Tracker.handle` and `_remember_frame`. Preserve `px_per_point` compatibility while exposing per-axis scales as needed. Validate new geometry before interpretation.
- [ ] Add a pipeline test where the same item is resized, moved, or transitions from legacy to window capture. Assert resolver runs again and activity receives no cross-geometry pixel diff; ensure the later same-item fallback cannot reintroduce that diff. Keep content extraction bounded to the isolated source.
- [ ] Run focused geometry, resolver, activity, content and memory-pipeline tests; confirm pass and commit shared mapping integration.

### Task 4: Whole-flow verification and handover

**Interfaces:** Existing CLI, replay, input evidence and memory storage remain externally compatible.

- [ ] Run `.venv/bin/python -m unittest discover -s tests -v`, syntax compilation and `git diff --check`. Use macOS-capable execution for native OCR tests. Fix actual regressions and add focused regression tests for any discovered failure.
- [ ] Obtain one independent whole-change review using the requesting-code-review skill. Review selection/privacy boundaries, capture ownership, metadata compatibility and activity reuse; resolve findings and rerun affected checks.
- [ ] Update README/HANDOVER/context with window capture behavior, Accessibility fallback, spanning/offscreen skips, legacy compatibility, test evidence and explicit privacy limits. Mark completed tasks; keep unevidenced live QA open.
- [ ] Provide the short live script: start one tracker, view Safari body text, edit a file, open a focused dialog, move the window to a second display if available, then stop. Inspect accepted image boundaries/metadata/OCR and named skips. Do not start a listener, microphone or private-data replay merely to claim live acceptance.
- [ ] Commit final verification/documentation. Report automated results separately from pending live acceptance and publication state.

## Review and execution state

Written spec approved by user (“go for it”). Plan self-review complete: each spec requirement maps to Tasks 1–4; native assumptions have explicit fixture/live checks. Product implementation has not started. Preserve the previously selected native execution method: implement in this session, then obtain one independent whole-change review. Written-plan review is pending.
