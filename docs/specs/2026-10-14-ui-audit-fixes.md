# UI audit fixes (Kowalski skills audit)

Source: `design/ui-audit-emilkowalski.md` in the project files (audit of every screen against `emil-design-eng`,
`review-animations` and `apple-design`). This change fixes what can be fixed from code that is checked by tests and a
fake-AppKit smoke run. **None of it has been run on a Mac yet**: see "Needs a look on the Mac".

## What changed

| Audit item | Change | Where |
|---|---|---|
| No hover or press state; action fired on mouse-down | `_Control` base: hover wash, pressed wash, fires on mouse-up inside, drag away cancels. `_Tap` and `_KitButton` both use it | `widget.py` |
| Custom controls invisible to VoiceOver, no Tab, no focus ring | `_Control` is an AXButton (or AXCheckBox for note ticks, with its value); `_KitButton` takes Tab, shows the focus ring, Space/Return press it; `_KitText` speaks its own words outside a control; the pill is an AXButton that says its state | `widget.py`, `setup_kit.py` |
| ⌃⌥N note card animated (keyboard, 100+/day) | Appears at once | `notecard.py` |
| Pill card: fade only, no origin; opened from keyboard too | 140 ms ease-out grow from the pill (scale 0.97 + opacity). No animation when a shortcut opened it. Exit stays instant | `widget.py`, `motion.py` |
| Dialogs and toast appeared instantly | Scrim fades; dialog pops (0.96 → 1, 200 ms, centred); toast pops in | `window.py` |
| Setup screens swapped with no direction | 220 ms push: forward from the right, Back from the left | `onboarding_ui.py` |
| Celebration fade 0.6 s on the default curve | 250 ms on the shared curve | `widget.py` |
| Reduced motion not handled | One check (`motion.reduced()`): fades stay, scale and push are dropped | `motion.py` |
| Orange marks on the light pill 2.1–2.8:1; red 3.7:1; blue words on dark card 3.6:1; blue button 4.4:1 | Colours in `palette.py`, held by `tests/test_palette.py` (marks ≥ 3:1, text ≥ 4.5:1) | `palette.py`, `widget.py`, `notecard.py`, `setup_kit.py` |
| 10–11 pt tertiary-grey labels | Secondary grey, 11 pt minimum for section labels | `widget.py`, `notecard.py` |
| Hit targets 16–24 pt (Back, link rows, Undo) | 24–28 pt | `widget.py` |
| Large titles had no tracking | −0.02 em at 24 pt and above | `setup_kit.py` |
| Three "selected" styles | Selected tab and period are filled (primary) everywhere | `window.py`, `memory_pane.py` |
| Settings showed Pause and Resume together | Removed there; the Memory tab shows the one that applies | `window.py` |
| Delete next to Quit in the menu-bar menu | A divider between them | `menu_model.py` |
| Static focus ring in the app picker | Drawn while the search field has the cursor | `onboarding_ui.py` |
| Memory tab: a dozen identical buttons, JSON dump, developer wording | New `memory_pane.py`: status dot with Pause/Refresh on top, evidence as cards, notes, then a folded "Connections and setup" in small groups (model, VS Code, Codex, Stop). The preview is monospace in a scrolling box. Cutting-off actions use the heavier outline, not red (red stays for a permission that is off) | `memory_pane.py`, `memory_view.py` |

## Decided, not done

- **Page changes in the window do not animate.** They happen tens of times a day; the skill says to leave those instant.
- **The pill card's exit is instant.** Exit faster than enter; instant is the fastest.
- **Accent stays blue in the window.** `tests/test_setup_assets.py` records that as an earlier decision. Say the word to move it to orange.

## Not done yet

- Pill: replace the panel-frame resize with a fixed panel and an animated capsule layer (removes the hover flicker workaround). Needs a Mac to tune.
- Finished-note fold collapsing its height instead of vanishing.
- One app mark and one typeface (Figtree in windows, system font on the pill) across all surfaces.
- Whole-view rebuilds on every state change (the reason most motion is limited to arrivals).
- Unicode glyph icons (`○ ✓ ▾ ▸`) to SF Symbols; tooltips for truncated names.
- Tab through the window's rows (only buttons take Tab; rows keep arrow-key navigation).

## Needs a look on the Mac

Press and hover feel; the Tab order and focus ring; VoiceOver reading the pill, note ticks and Settings; the pop on the
pill card and dialogs (and that reduced motion turns the scale off); the setup push; contrast over real wallpapers;
the Memory tab at 880 px wide with real data; a click that lands while the window re-renders (the control is rebuilt
between mouse-down and mouse-up, which could drop it).

## Follow-up after the Mac run

- Setup window: resizable (min 480x600), the column is centred in a `stage` view, and a body taller than the room scrolls above the pinned Continue button.
- Memory tab: Enable button label shortened and clamped to the column; `MemoryController.busy` shows "Enabling Memory..." until the answer, an error or a restart.
- `Tracker.window_memory_action` takes the shared lock only for notes, so the main thread never waits on it. The hang itself was not reproduced; verify on the Mac.
