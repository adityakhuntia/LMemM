# First-run setup

**Date:** 9 October 2026 · **Branch:** `feat/first-run-onboarding` · Mock-up: "LMemM First Run" artifact

## Problem

A new customer opens LMemM and nothing tells them what it is, who it is for, or which macOS
permissions it needs. Today the tracker exits with a terminal message if Screen Recording is off.
This is the customer's first impression: few screens, one idea each, no way to get stuck, and every
failure has a calm recovery.

## The screens

| # | Screen | One idea | Main button |
|---|---|---|---|
| 1 | welcome | what LMemM is, in one line; everything stays on this Mac | Get started |
| 2 | you | first name (required, starts empty), what you mostly work on (optional) | Continue (needs a name) |
| 3 | access | Voice notes, Accessibility (optional), Screen Recording (needed, last) | Continue (always works) |
| 4 | try | press ⌃⌥N, see the note card (a rehearsal; nothing stored) | Show me / Skip for now |
| 5 | done | the pill appears | Done (or Restart LMemM / Not now) |

## Rules (all in `src/onboarding.py`, tested in `tests/test_onboarding.py`)

- **S1** Nothing can trap you. Back everywhere except screen 1. Every main button works except
  Continue on "you" while the name is empty. Tested for every combination of permission states and
  with a seeded random walk of 300 runs × 80 presses.
- **S2** Only a name is required. Name, roles and apps change only on their own screens.
- **S3** A permission's state is read from macOS, never remembered: `granted`, `off`, `denied`
  (voice only), `restart` (Screen Recording is on for a new process but not this one).
- **S4** Screen Recording is last, so one restart covers everything. A restart resumes on the same
  screen with the same answers (`data/onboarding.json`, written on every press).
- **S5** "Only some apps" is a list of bundle ids; an empty list is every app.
- **S6** The `user` block in memory.json is written once, on Done (or Not now).
- **S7** Setup runs once.
- **S8** The window (`onboarding_ui.py`) draws `Setup.view()` and forwards presses; it decides nothing.
- **R11** (`rules.py`) An app you did not choose is never captured, read or remembered. Checked in
  `Tracker.capture` and `identify_now` before anything is looked at (`tests/test_tracker_gate.py`
  keeps that order). The pill shows one neutral mark; ⌃⌥N opens a card that says so.

## What is stored

```json
"user": {"name": "Ada", "works_on": ["code"], "watch_apps": [{"id": "com.google.Chrome", "name": "Chrome"}],
         "language": "en-IN", "time_zone": "Asia/Kolkata", "set_up": "2026-10-09", "onboarding": 1}
```

`works_on` and `watch_apps` appear only when chosen. `store.save_memory` writes the block back on
every save; `store.save_user` never overwrites a damaged memory file.

## Permissions (checked against the code)

| Permission | Used by | In setup |
|---|---|---|
| Screen Recording | `macos.screen_recording_allowed` (tracker) | needed; restart after turning on |
| Microphone + Speech Recognition | the "LMemM Listen" helper | one row, two prompts; typing works without |
| Accessibility | `ax.read` returns nothing unless trusted | optional; no restart |
| Automation | browser tab address (AppleScript) | not in setup; macOS asks per browser |
| Input Monitoring | opt-in input timeline only | not needed |

The hotkey is Carbon `RegisterEventHotKey` and needs no permission.

## Mac-side pieces (cannot run in CI; checked by hand on a Mac)

- `permissions.py`: preflight calls, a fresh-process check for the restart case, System Settings
  deep links. Opening the Screen Recording or Accessibility pane first asks once, so LMemM appears in
  the list to switch on.
- `native/listen/listen.m`: `--status` (never asks) and `--authorize` (asks Speech, then Microphone).
- `onboarding_ui.py`: the window, the app picker (icons from macOS), the rehearsal card.
- Restart is `os.execv` of the same command, so macOS sees the same app.

## Behaviour changes outside setup

- With setup finished, the tracker no longer exits when Screen Recording is off; it keeps running,
  the pill shows the red mark, and the terminal says how to fix it. Without finished setup (for
  example `--no-setup`) it exits as before.
- `dictation.register_hotkey` and `start_app` are safe to call twice (setup, then the tracker).

## Not done / open

- Real app icons and the pill appearing on the "done" screen are not in the window (the pill starts
  after Done).
- A packaged, signed .app. Permissions still attach to the terminal that launched LMemM.
- A menu-bar "Check access" entry (setup can be reopened with `setup --again`).

## Look and type (rev. 2)

- Type is Figtree (`assets/fonts`, SIL OFL), registered for the process; the system font is the fallback.
- Highlight is blue (`setup_kit.ACCENT`), not the pill's orange. Selected chips are blue with white text.
- The name field starts empty (placeholder "First name"); Continue stays off until there is a name.
- All text is drawn by `setup_kit` (centred on both axes in buttons); headings and notes are centred.
- Role chips carry an SF Symbol each; the "That's a note." confirmation sits in a soft green box.
- `lmemm.py setup` ends by starting LMemM, so the pill is on screen after Done.
