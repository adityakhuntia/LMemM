# Architecture

One process, two threads, plain files.

```
 macOS ──▶ macos.py ──▶ tracker.py (main thread) ──queue──▶ tracker.py (resolver thread)
           front window,     when to capture:                 resolver.py   OCR + layout
           browser tab,      switches, timer, pins,           understand.py what you're doing
           screenshot,       notes, pause, idle                activity.py   typing/reading/…
           input counters                                      identity.py   which thing
                                                               memory_content.py excerpts
  ⌃⌥N ──▶ dictation.py ──▶ notes.py ◀──────────────────────────┘
                                │                         store.py ──▶ data/memory/*.json
  opt-in ─▶ input_monitor.py ─▶ input_events.py ─▶ input_store.py ──▶ data/memory/inputs, contributions
```

## Modules

| Module | One job | Talks to macOS? |
|---|---|---|
| `config.py` | tunables, privacy skip-lists, data paths (`config.paths()`, `config.use_paths()` for tests) | no |
| `macos.py` | front window, browser URL, displays, screenshot, idle/input counters, pointer, notifications, workspace events | **yes** |
| `tracker.py` | orchestration: schedule captures, run the resolver thread, keep the timeline, apply controls, resurface notes | via `macos` |
| `resolver.py` | screenshot → objects with text, kind, box, entities (Apple Vision) | Vision |
| `understand.py` | objects + URL/window → app, action, target, details (per-app rules) | no |
| `activity.py` | two frames of one thing → changed regions, scroll, activity category | no |
| `identity.py` | which memory item a screen is: same thing vs. new thing | no |
| `memory_content.py` | bounded excerpts + unverified decision quotes | no |
| `notes.py` | notes: record/attach, ids, done-state, resurfacing rule, project view | no |
| `store.py` | load/save `.index.json`, readable `memory.json` / `pending.json`, sessions | no |
| `dictation.py` + `listen/` | ⌃⌥N hotkey (Carbon), note window, on-device speech helper app | **yes** |
| `widget.py` | the on-screen pill and its Left / Plan card (non-activating panels) | **yes** |
| `input_monitor.py` | opt-in listen-only event tap + privacy gate | **yes** |
| `input_events.py` | input summaries, ordering, context boundaries | no |
| `input_store.py` | input files, capture links, provenance, session deletion | no |
| `lmemm.py` | CLI | no |

Rules that keep this cohesive:

- Only `macos.py`, `dictation.py`, `widget.py`, `input_monitor.py` and `resolver.py` touch macOS APIs,
  so everything else is testable with plain data.
- Nothing imports `tracker` or `lmemm`. Dependencies point inward toward `config`.
- Paths come from `config.paths()` at call time, never module globals. Tests point
  everything at a temp directory with `config.use_paths(dir)`.
- `.index.json` is the source of truth. Readable files are derived from it on every save.
  New fields are additive (schema 2).

## A screenshot's life

1. **Trigger** (`tracker.tick`, ~4×/s): a workspace notification, a title/window change
   (one CGWindowList call), the timer, a pin, a note, or input activity. Triggers wait
   `SETTLE` s so a burst of switches becomes one capture.
2. **Capture** (`tracker.capture`): skip-list check, screenshot of the window's display,
   re-check that the front window didn't change, write `<ts>.jpg/json`, enqueue.
3. **Resolve** (resolver thread, `tracker.handle`): if the pixels didn't change since the
   last frame of the same window, reuse its OCR. Otherwise OCR → `understand.describe`.
   OCR runs outside the memory lock, so saving a note never waits for Vision.
4. **Remember** (`tracker.remember`, under the lock):
   `identity.resolve_item` → `activity.classify` → update the item, keeping one
   screenshot per thing and dropping redundant frames → extend or start a timeline
   event → **resurface** open notes on a new visit → attach notes waiting for this
   frame → `store.save_*`.

## Notes as pending edits

- `notes.record` stores a note on the item its capture resolved to. Until then it's
  `pending` in the session file.
- A note never changes after it's written. Done-state lives in `item.notes_done`
  (`{note id: when}`), because provenance (`input_store`) matches notes by value.
  Note ids are `sha1(at|text)`, so old notes get them without migration.
- Reminders fire only when you **come back**. When a timeline stretch starts, the
  tracker checks the previous stretch. If it was this same thing, split only by the note
  window, the card, a pause or a lock, that's not a return. `notes.due_for_resurfacing`
  then needs open notes, and either no reminder within `RESURFACE_COOLDOWN` or a note
  added since the last reminder.
- `notes.project_of` derives the project. `notes.pending_view` builds the grouped view
  for both the CLI and `pending.json`.
- `lmemm.py notes done` goes through the running tracker's control file (applied under
  its lock). If the tracker is stopped, it writes `.index.json` directly and records a
  provenance contribution so session deletion stays consistent.

## The pill (widget.py)

- It runs inside the tracker process, on the main thread. Its panels are borderless and
  non-activating, at status-window level, on all Spaces, so clicking them never takes
  focus from the app you're in.
- `Tracker.widget_card()` hands it `notes.card(items, current item)` for the last thing
  you were on. That gives the project, the **left** edits (this thing first), the full
  **plan** (open, then done) and the **history** (added / done, newest first). Ticking a
  box calls `Tracker.widget_tick`, which runs `notes.set_done` and saves under the lock.
- `tick()` refreshes the pill's dot about once a second. While the card is open, it skips
  capture, so the card never gets OCR'd into memory.

## Talking to a running tracker

`.lmemm.pid` names the process. `lmemm.py pause|resume|notes done` write a PID-scoped
`.lmemm.control.json`, which the tracker applies on its next tick. `status` reads
`.lmemm.status.json`. `pin` and `note` use SIGUSR1 / SIGUSR2.

## Extending

| You want to… | Change |
|---|---|
| teach it a new app or site | a rule in `understand.py` (`describe`), plus a `KINDS` entry |
| give a thing a reliable identity | set `stable_identity` in its `understand` rule (see Google Docs) |
| change capture timing or skip-lists | `config.py` |
| group pending edits differently | `notes.project_of` |
| store something new per thing | set it in `tracker.update_item`; show it in `store.readable` |

## Testing

`python3 -m unittest discover -s tests` runs 110 tests: real Vision OCR on generated
images, identity, content, migration, notes/resurfacing/project view, the CLI, input
events with fake native data, retention and deletion recovery. No test uses the real
microphone, input tap or your data.
