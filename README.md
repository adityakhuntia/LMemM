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

## What you get

Everything goes in `data/`:

- `data/memory/memory.json`: one entry per thing, across all sessions. It holds
  the latest state (e.g. an email's to / subject / draft), time spent, visits,
  and one screenshot.
- `data/memory/sessions/<session>.json`: the timeline of what you were on and when.
- `data/<ts>.jpg`: the one screenshot kept per memory entry. Screenshots that
  showed nothing new are deleted.

## Files

| File | What it does |
|---|---|
| `lmemm.py` | the one command: start, `memory`, `pin`, `peek` |
| `tracker.py` | watches macOS for app / tab / window changes, takes screenshots, keeps the memory |
| `resolver.py` | reads each screenshot: text + layout (Apple Vision, on-device) |
| `understand.py` | rules that turn a screen into "what you're doing" (Gmail, chats, AI apps, editors, browser, ...) |
| `run.sh` | background start / stop |
| `logger.py`, `peek.py` | the earlier fixed-interval logger and its summary (still work on their own) |
