# LMemM — Large Memory Model (prototype)

Watches what you do on your Mac and keeps a small memory of it: which app you
were in, what you were doing there, and what it was about. One entry per thing
(an email draft, a document, a chat, a file), updated when you come back to it.
Everything runs locally on your Mac. Nothing is sent anywhere.

## Setup (once)

macOS only. Needs Python 3 with pyobjc:

```bash
cd LMemM
pip3 install -r requirements.txt
```

Grant your terminal app (Terminal, iTerm, VS Code, ...) these permissions in
**System Settings → Privacy & Security**, then quit and reopen it:

- **Screen Recording**: needed for screenshots and window titles.
- **Automation**: macOS asks the first time it reads a browser's URL. Allow it.

## Use

```bash
python3 lmemm.py             # start; Ctrl-C to stop
python3 lmemm.py memory      # see what was remembered
python3 lmemm.py pin         # (in another terminal) force-save the current screen
```

While it runs it prints one line each time what you're doing changes:

```
22:16:23  timer        Gmail      Looking through the inbox (1,792 unread)
22:16:28  timer        Gmail      Writing an email to Aditya Gupta (gmail.com) (no subject yet)
22:16:52  app_switch   VS Code    Editing lmemm.py in LMemM   (back to it)
```

To run it in the background instead:

```bash
./run.sh start      # start
./run.sh log        # watch it
./run.sh status     # is it running
./run.sh stop       # stop and print the session summary
./run.sh memory     # see what was remembered
```

## When it takes a screenshot

- When you switch apps, tabs or windows (after waiting ~1s for the screen to settle)
- Every 5s while you stay on the same window (`python3 lmemm.py --every 10` to change)
- Never while idle for 60s+, locked, or asleep
- Never in password managers, private/incognito windows, or banking, payment and login
  pages (lists at the top of `tracker.py`)

## What it notices inside an app

Each screenshot is compared with the previous one of the same thing. Only the
parts that changed are looked at, plus three system counters (seconds since
the last key press, scroll and click, never *which* key) and where the pointer
is when the screenshot is taken. That gives one of four activities for each
moment, in any app:

| Activity | Means | Example |
|---|---|---|
| **typing** | you pressed keys and text was edited in place (a line grew, or replaced a placeholder) | writing an email body, a prompt, a doc |
| **reading** | the view scrolled, or nothing changed while you stayed on it | scrolling an article, reading a thread |
| **receiving** | new text appeared with no input from you | a chat message arriving |
| **focus** | you clicked or pointed and that area changed | opening menus, switching panels |

A screenshot with no pixel changes skips text reading entirely. Text already on
screen when you arrive (old messages, earlier parts of a doc) is not recorded as
something you did; UI noise (placeholders, "online", timestamps) is ignored.

## What you get

Everything goes in `data/`:

- `data/memory/memory.json`: one entry per thing (an email draft, a doc, a chat,
  a file, a page), across all sessions. Each entry has:
  - `doing`: one line, e.g. *Writing an email to Aditya Gupta, subject "Testing"*
  - `mostly`: which activity took most of the time on it
  - `state`: its latest content (e.g. an email's to / subject / draft)
  - `activity`: seconds spent typing / reading / receiving / focus, and the text
    involved in each (what you typed, what you scrolled past, what came in)
  - time spent, visits, updates, and its one screenshot

  **Same thing or a new one?** One rule for every app, based on what you typed:
  if your earlier text is still on screen, it's the same thing (even if its URL
  or title changed while you stayed on it). Otherwise a new name means a new
  thing: two chats in one WhatsApp tab are two entries. If your text vanished while you
  stayed there without scrolling, or you come back and the spot you typed into
  is empty, it's a *new* thing that only looks the same: a second email, a new
  note, a fresh prompt. Chats and threads (anything that received text from
  others) never split.
- `data/memory/sessions/<session>.json`: the timeline of what you were on and when.
- `data/<ts>.jpg`: the one screenshot kept per memory entry. Screenshots that
  showed nothing new are deleted.

## Files

| File | What it does |
|---|---|
| `lmemm.py` | the one command: start, `memory`, `pin`, `peek` |
| `tracker.py` | watches macOS for app / tab / window changes, takes screenshots, keeps the memory |
| `resolver.py` | reads each screenshot: text + layout (Apple Vision, on-device) |
| `activity.py` | compares each screenshot with the last one: changed regions, scrolling, typing / reading / receiving / focus |
| `understand.py` | rules that turn a screen into "what you're doing" (Gmail, chats, AI apps, editors, browser, ...) |
| `run.sh` | background start / stop |
| `logger.py`, `peek.py` | the earlier fixed-interval logger and its summary (still work on their own) |
