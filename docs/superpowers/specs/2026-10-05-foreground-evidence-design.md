# Foreground-window evidence quality

Date: 2026-10-05. Status: proposed design; implementation not started.

## Purpose and success criteria

Retain the work in the foreground window consistently. A screenshot, its OCR,
pointer coordinates, content excerpts, and activity comparison must describe the
same source area. This addresses the observed Safari toolbar-sized selection and
the current full-display screenshot exposure. Preserve historical memories and
the existing input privacy gates.

Success means a verified browser/editor window supplies body content, a focused
dialog is not replaced with a larger window, unrelated windows are absent from
new saved pixels, and changed/unknown geometry cannot silently reuse old OCR.
It does not establish authorship or turn observed decision quotes into decisions.

## Approach

Use a verified window-server ID and capture that window directly with the local
`screencapture` tool. Its installed help documents `-l` for window IDs, `-o` to
omit shadows, and `-a` to exclude attached windows. Do not capture a whole display
and crop it after persistence.

Alternatives considered:

- Keep display capture and improve rectangular OCR filtering: easiest, but
  unrelated source pixels would still be persisted, and overlapping windows
  could be attributed to the foreground app.
- Introduce ScreenCaptureKit and a native streaming service: useful for a later
  capture product, but adds lifecycle/build machinery beyond this existing
  screenshot flow. No new streaming subsystem is needed for this increment.

## Focus and window selection

Add a small capture-geometry module with pure selection/validation functions and
a read-only macOS AX adapter. Query the foreground process's focused window,
position and size. Do not read editable values, selected text or field contents.

Match finite, positive AX geometry to exactly one on-screen, layer-zero window
owned by the foreground PID. Permit at most two points of edge discrepancy.
No unique match means no capture. Window title is supplementary metadata, not
the primary matching key. Small focused dialogs remain eligible; eliminate the
current arbitrary 80-point minimum and first-window choice.

When Accessibility permission is absent, permit a clearly labelled fallback
only if the window server supplies exactly one eligible window for that PID.
Do not choose the largest window or silently fall back after an AX error,
unsupported focused-window attribute, ambiguous match, or changed process.
Unknown focus/geometry produces a capture-skip reason and count. Rate-limit
repeated messages so a timer does not flood the terminal.

This fallback improves compatibility without claiming verified focus. Existing
input collection still requires its stronger independent role/owner/security
checks. Do not broaden its app allowlist or weaken any failure gate.

## Source pixels and display geometry

For new captures call `screencapture -x -o -a -t jpg -l WINDOW_ID PATH`, followed
by the current long-edge downscale. Check command success, image validity and
aspect ratio against the selected point bounds before publishing metadata.
Delete rejected output and never enqueue it or copy it into input evidence.

The source is the selected window surface, including its own chrome. It can
contain content obscured by another window; it is not a promise to capture only
currently visible screen pixels. Other windows and attached windows are excluded.
AX/window-server mismatches involving sheets or dialogs must skip capture rather
than guess an attachment relationship.

First-slice support covers windows fully contained in one display, including a
display above or to the left of the primary display. Reject partially off-screen
windows and windows spanning displays with an explicit reason. This avoids
claiming a reliable single scale across mixed-DPI displays. Later support may
extend this once pixel mapping is evidenced.

Use the menu-bar display's height once to convert Cocoa display rectangles and
pointer positions into the same global top-left point coordinates as CG and AX.
Subtract the captured window's origin to obtain local pointer points. A pointer
outside that window becomes null. Do not store a pointer belonging to another
display/window as foreground evidence.

## Metadata and compatibility

New metadata carries `capture.version = 2`, `capture.mode = window`, selected
window ID, global source bounds in points, selection method, display bounds,
and actual image dimensions. Set `window_region` to `[0, 0, 1, 1]` for the isolated
window image. Define `screen.w/h` as source point dimensions for new frames and
retain actual display geometry separately. These fields must be documented as
versioned semantics, not silently reinterpreted for historical frames.

A shared mapping helper supplies independent x/y pixel-per-point scales from
validated source bounds and image dimensions. Resolver focus and activity
pointer calculations use it. Missing or malformed version-2 geometry fails
processing explicitly; it must not fall back to full-display interpretation.

Frames without `capture.version` keep the existing display-local interpretation,
including historical `window_region` and pointer/cursor fields. Do not rewrite
old metadata, screenshots, contributions or item IDs. No memory-index schema
migration is required. Replay supports both formats.

## Stable capture and comparison boundaries

After capture, re-read foreground PID, bundle, window ID/title and bounds. For
browsers, also re-read URL, tab title and private-context status. Any missing or
changed context discards the image and schedules a fresh settled capture.
Apply this to all capture triggers, not only dictated notes.

Include source version/mode/bounds and image dimensions in the frame comparison
signature. A move, resize or change between legacy display and window capture
forces fresh OCR and breaks pixel/activity comparison. Resolving to the same
memory item does not override this boundary. Do not interpret resize/reframing
as typing, scrolling or received content.

Retain existing monotonic capture intervals and context IDs for input linkage.
Copy only accepted window images into the input source store. Preserve pending
note ownership, pause, sensitive-context filters, provenance and deletion flow.

## Verification

Use test-first changes for selection, projection and lifecycle behavior:

- Safari-sized auxiliary window before the actual AX-focused browser window;
  a legitimate small focused dialog; duplicate geometry; missing/invalid AX;
  permission-absent unique fallback and ambiguous fallback rejection.
- Displays with negative origins and above-primary placement; Retina/non-Retina
  x/y scaling; inside/outside pointer; spanning/off-screen rejection.
- Exact window-only capture arguments, command/image failure cleanup, changed
  bounds/foreground/browser/private state, and no rejected-image input copies.
- Legacy and version-2 resolver/content fixtures; fresh OCR and no activity diff
  across geometry changes even when the memory item is unchanged.
- Existing input, identity, notes, provenance and native OCR regression suite.

After automated checks, use a short explicitly initiated live sequence with
Safari body text, an editor and a dialog, plus a second display if available.
Inspect image boundaries, OCR body content, metadata dimensions and skip reasons.
Report automated verification separately from live acceptance; do not claim
live coverage from mocked command or AX tests.

## Out of scope and follow-up

No pane-level tracker-log removal, password-field redaction inside an otherwise
allowed window, encryption, broader keyboard recording, semantic recall, agent
API, or UI is included. Local window isolation reduces unrelated pixels but
cannot make all captured content private by itself. Existing sensitive app/site
filters and plaintext-storage disclosures remain necessary.

Next: improve self-observation/authored-text attribution and time accounting,
then reliable project/file identity and source-backed project recall. Multi-display
straddling and sheet ownership require dedicated native evidence before support.

## Native API references

- [Apple AX position coordinates](https://developer.apple.com/documentation/applicationservices/kaxpositionattribute)
- [Apple window information](https://developer.apple.com/documentation/coregraphics/cgwindowlistcopywindowinfo(_:_:))
- [Apple CG window bounds coordinates](https://developer.apple.com/documentation/coregraphics/kcgwindowbounds)
- Installed `/usr/sbin/screencapture` usage on this development Mac.
