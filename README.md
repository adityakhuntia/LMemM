# LMemM — Large Memory Model (prototype)

A memory layer for your Mac. LMemM watches what you work on and keeps **one memory
entry per thing** — an email draft, a doc, a chat, a code file, a page — with what
you did there (typing, reading, receiving, focus) and what it was about. Press
**⌃⌥N** anywhere to say a note about the thing in front of you; it becomes a
**pending edit** that comes back when you reopen that thing.

Everything runs on your Mac: capture, OCR (Apple Vision), activity rules and speech
recognition. No model or server is involved.

## Setup (once)

macOS only. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Then give the app you launch it from (Terminal, iTerm, VS Code…) these permissions in
**System Settings → Privacy & Security**, and quit/reopen that app:

| Permission | Needed for |
|---|---|
| **Screen Recording** | screenshots and window titles (required) |
| **Automation** | reading the browser tab's URL (macOS asks the first time) |
| **Microphone**, **Speech Recognition** | voice notes; asked for "LMemM Listen" the first time you press ⌃⌥N |
| **Input Monitoring**, **Accessibility** | only for the opt-in input timeline |

The speech helper is built with clang (Xcode Command Line Tools) on first run.

## Use

```bash
python3 lmemm.py                      # start watching; Ctrl-C to stop
python3 lmemm.py memory               # what's remembered + the latest session
python3 lmemm.py notes                # pending edits, by project
python3 lmemm.py notes done n-3f9a1c  # tick one off (reopen: notes reopen ID)
```

| Command | What it does |
|---|---|
| `lmemm.py [start] [--every N] [--no-widget]` | watch and remember; capture every N s on the same window (default 5) |
| `lmemm.py memory [N] [--content] [--events]` | latest N things; `--content` adds kept excerpts, `--events` the input timeline |
| `lmemm.py notes [--all] [PROJECT]` | open notes grouped project → thing; `--all` includes done ones |
| `lmemm.py notes done ID…` / `notes reopen ID…` | mark notes done / open again |
| `lmemm.py status` / `pause` / `resume` | the running tracker; pause stops all capture |
| `lmemm.py pin` | force-save the current screen |
| `lmemm.py note` | open the note window from a terminal (same as ⌃⌥N) |
| `lmemm.py delete-session ID --dry-run` / `--confirm ID` | remove one session's evidence |
| `./run.sh start` / `stop` / `log` / `status` | the same tracker, in the background |

While it runs you see one line per change in what you're doing:

```
LMemM is watching  ·  captures on app/tab switches, else every 5s  ·  pauses after 60s idle
⌃⌥N dictate a note  ·  Ctrl-C stop

10:02:13  Google Docs     Working on "Q3 plan"
10:02:41  Google Docs     note saved
10:03:05  Gmail           Looking through the inbox (1,792 unread)
10:09:12  Google Docs     Working on "Q3 plan"  (back to it)
10:09:12                    📝 1 pending edit: add a pricing table
```

## Notes and pending edits (⌃⌥N)

Press **⌃⌥N** in any app. A small window opens for what's in front ("Note for: Google
Docs: Q3 plan") and it is **already listening**: talk, and your words appear as you
speak. You can type or fix words too. **Return** saves, **Esc** cancels.

- The note goes on the memory entry for that thing, kept apart from what LMemM
  observed. If OCR hasn't caught up yet, it waits for that screen; it never lands on
  the previous thing.
- Every note is a **pending edit** until you mark it done.
- **Resurfacing:** when you come back to a thing with open notes, LMemM shows a macOS
  notification and a terminal line, at most once every 10 minutes per thing.
- **Project view:** `lmemm.py notes` lists open edits by project: a code file's project
  folder, a document, `Email`, `Chats`, `AI chats`, a website, or the app. The same view
  is written to `data/memory/pending.json`.

```
2 pending edits

LMemM  (1 open)
  VS Code         tracker.py
      n-8c21d0  • split capture out of tracker   (2026-10-06 10:01)

Q3 plan  (1 open)
  Google Docs     Q3 plan
      n-3f9a1c  • add a pricing table   (2026-10-06 10:02)
```

## The pill

A tiny translucent bar sits at the bottom of your screen, like Wispr Flow. It never
takes focus and shows over every app, Space and full-screen window. An orange dot
means the thing you're on has edits left.

Click it for a small card about the project of whatever you're on:

- **Left** shows the edits still to do, with this thing's first. Tick one and it's done,
  so next time you only see what's left.
- **Plan** shows every note on the project (open, then done, each with when) and its
  history: notes added and ticked off, newest first.

Click the pill again, or ×, to close it. Start with `--no-widget` to hide it.

## What it remembers

**When it captures:** on app, tab and window switches (after ~1 s to settle), every 5 s
on the same window, and on input bursts if the input timeline is on. It pauses when
you're idle 60 s, locked, asleep or paused, and never captures password managers,
private/incognito windows, or banking, payment and login pages (`config.py`). A screen
with no pixel change since the last one skips OCR.

**What it works out per screen:**

- **What you're doing** — per-app rules: Gmail (inbox, reading, composing, writing),
  chats, AI assistants, editors, docs, search, YouTube, any page or app.
- **Which thing it is** — a Google Doc by its id; otherwise by place plus what you
  typed there. Two chats in one WhatsApp tab are two things; a second email in the same
  compose slot is a new thing; a draft that gets saved or renamed stays the same thing.
- **What happened since its last screen** — from the changed pixels and three system
  counters (seconds since the last key press, scroll and click, never which key):

| Activity | Means |
|---|---|
| **typing** | you pressed keys and text was edited in place |
| **reading** | you scrolled, or nothing changed while you stayed |
| **receiving** | new text appeared with no input from you |
| **focus** | you clicked or pointed and that area changed |

**Where it goes** (`data/`, never committed):

| File | Contents |
|---|---|
| `memory/memory.json` | every thing, readable: what, doing, project, your notes (with status), latest content, activity, time, its one screenshot |
| `memory/pending.json` | open notes by project |
| `memory/sessions/<id>.json` | one session's timeline: when you were on what, and what was resurfaced |
| `memory/.index.json` | full internal state (source of truth — back this one up) |
| `memory/inputs/`, `memory/contributions/` | input timeline and per-session evidence (see below) |
| `<ts>.jpg` / `<ts>.json` | the one screenshot kept per thing, and its capture metadata |

One entry looks like:

```json
{
 "id": "document-1a2b3c4d", "app": "Google Docs", "project": "Q3 plan",
 "what": "Q3 plan", "doing": "Working on \"Q3 plan\"",
 "your_notes": [{"id": "n-3f9a1c", "at": "2026-10-06 10:02", "text": "add a pricing table", "status": "open"}],
 "mostly": "typing",
 "activity": {"typing": {"time": "2m 10s", "text": ["Pricing", "Three tiers: …"]}, "reading": {"time": "40s"}},
 "time": {"total": "2m 50s", "visits": 3, "first": "2026-10-06 10:01", "last": "2026-10-06 10:09"},
 "screenshot": "20261006-100912.jpg"
}
```

## Input timeline (opt-in, VS Code only)

```bash
python3 lmemm.py --input-events --input-app com.microsoft.VSCode
```

Records timestamped keyboard **bursts and counts** (never characters), coarse cursor
regions, clicks, scrolls and Ctrl/Cmd+Tab steps, linked to screenshots and memory
entries. It is kept for at most 24 h. Details, the privacy model, and how session
deletion works are in [docs/input-timeline.md](docs/input-timeline.md).

## Privacy, briefly

- Nothing leaves the Mac. Files are plaintext JSON/JPEG under `data/`, which git ignores.
- Screenshots are whole displays. The skip-lists use foreground checks, so other
  windows on screen can still be captured.
- Voice: on-device recognition only; the helper runs only while the note window is
  open and keeps no audio.

## Develop

```bash
python3 -m unittest discover -s tests      # 104 tests, incl. real on-device OCR
```

[ARCHITECTURE.md](ARCHITECTURE.md) covers how the modules fit and where to extend it.
[docs/](docs/) has specs, plans and the development history.
