# Event trail: knowing what you are doing from app events, not pictures

Status: draft, **not yet run on a Mac**. Tracking only; turning the trail into memory/context comes later.

## What it is

A second tracker, `lmemm.py trail start`, that works the way ChatGPT's Computer History does: it logs
**events** (app switches, window/title/focus/selection changes, clicks, typing bursts, shortcuts) and
reads **what apps expose through macOS accessibility** (window title, page URL, the message box's label,
headings, the selected sidebar row, visible text). No screenshots and no Screen Recording permission.
It runs beside the screenshot tracker; nothing in `tracker.py` changed.

Screenshots stay as a **fallback**: when an app exposes too little (a canvas, a game, some Electron
apps) and Screen Recording is already granted, one screen is read with Apple Vision, at most once per
20 s per place (`TRAIL_VISION*` in `config.py`). Without the permission that is a logged gap, not an error.

## Why chats were indistinguishable, and what changed

The window title of WhatsApp, Slack or ChatGPT is the same for every conversation. Now (`trail_place.py`):

1. **URLs with an id name the place exactly**: ChatGPT `/c/<id>`, Claude `/chat/<id>`, Gemini, Slack
   `/client/<team>/<channel>`, Discord, a Gmail thread, a Google Doc (and which sheet tab), a GitHub
   PR, a YouTube video. Tracking params and fragments do not create new places.
2. **No id** (WhatsApp, Messages, Telegram, Teams, WhatsApp Web...): the name is weighed from the message
   box label ("Type a message to Mum"), the selected sidebar row, the page heading and the window
   title. Agreement raises `confidence`; disagreement sets `conflict` and lowers it. Unread badges
   ("(3) Mum"), case and invisible marks do not make a new chat.
3. **A shaky read never flips the place** (`PlaceTracker`): a switch needs a certain signal (URL id, two
   agreeing signals, a new app) or has to repeat for 150 ms. A read that cannot name a chat keeps
   the chat already known in that app.

## Why it was slow, and what changed

| Before (screenshot tracker) | Now |
|---|---|
| timer every 5 s, plus a 0.1 s accessibility poll | no timer: macOS notifications (AXObserver on the front app, app switches) wake a worker |
| URL via AppleScript on the main loop (77 ms, once 9.6 s) | URL from the window/web area through accessibility; no AppleScript |
| one IPC per attribute | one `AXUIElementCopyMultipleAttributeValues` per node |
| every check reads everything | **light read** (title, URL, focused box: 3 calls) first; the tree walk only for an unsure place or the text read |
| unbounded | a read stops at 350 nodes or 45 ms; a hung app times out at 0.2 s |
| work on every change | changes inside 60 ms are one read (max wait 250 ms); text reads at most every 2 s per place; 5 s polling when idle, none for text |
| save everything per frame | events buffered, flushed every 1 s or 50 events, appended to a day file |

## What is recorded (`data/trail/YYYY-MM-DD.jsonl`, 0600, kept 48 h)

`app_switch`, `focus` (the place, why we think so, how long the last one lasted), `text` (only lines that
**appeared**, and how many left), `typing` / `scroll` (count + duration + which box, never the keys),
`click` (button, role and name of the control, e.g. "Send"), `shortcut` (a fixed list such as cmd+c, cmd+t,
ctrl+tab; other chords are ignored), `gap` (why nothing was recorded: paused, excluded app, secure field,
no accessibility, no screen access...).

Never recorded: typed characters, the contents of text boxes (`TRAIL_READ_FIELD_TEXT = False`; only
that a box exists and its label), password fields, anything from password managers, banks and similar
sites, private/incognito windows (`config.SKIP_*`), lines that look like secrets (card numbers, API
keys, long tokens). The app gate runs **before** any accessibility call, and an excluded app is
not even named in the log.

Controls: `trail pause|resume`, `trail forget --last 10 | --app NAME | --all`, `trail status`.
The per-app choice from first-run setup (PR #9, `apps.watched`) is honoured through
`Gate(watch_apps=...)`: when #9 merges, `trail_mac.Trail(watch_apps=...)` just needs the `user.watch_apps` list passed in
(`lmemm.py trail start` does not read memory.json yet).

## What was tested where

**Tested on Linux (69 tests, `tests/test_trail*.py`):** the tree walk against fake trees (order, budgets,
secure fields, typed text), every URL route, chat naming (two chats in one window, badges, conflicts,
unreadable chat, WhatsApp Web, Messages, unknown apps), place settling, the scheduler's debounce,
rate limit and idle behaviour (fake clock), the privacy gate and its order, the engine end to end with a
fake app (chat switch, text diff, redaction, gaps logged once, pause, typing counted not recorded,
screenshot fallback only when thin and rate-limited), the store (48 h expiry, boundary-day trim, forget,
size cap, torn line, file modes), and the CLI.

**Not run on a Mac:** `trail_mac.py` and `LiveNode` (they compile only): the AXObserver callbacks, the event
tap, the real attribute reads, Chromium `AXManualAccessibility`, the screenshot fallback, and every
**real-app rule** in `PROFILES` (WhatsApp, Messages, Slack, Discord, Telegram, Teams, VS Code...), which are
written from how those apps are documented to label things and need checking. **No latency number here is
measured**; the design numbers above are targets.

## For you to run on the Mac

```bash
python3 lmemm.py trail start            # grant Accessibility (+ Input Monitoring for clicks/typing)
python3 lmemm.py trail show 60          # switch chats in WhatsApp / ChatGPT tabs / Slack, then look
python3 lmemm.py trail places --hours 1
python3 lmemm.py trail status           # full_read_ms p50/p95, observer_notifications > 0 means notifications work
python3 lmemm.py trail probe            # in an app whose chats come out as the wrong name: saves its tree
```
Things to look for: (1) each chat switch is one `focus` line with the right name; (2) `observer_notifications`
is 6 for the app in front; if it is 0 the trail still works but at about 1 s delay; (3) `full_read_ms p95`
under ~45; (4) Activity Monitor CPU while you type and switch; (5) Chrome/VS Code feel the same (the trail turns on
their accessibility tree, which costs them some work; it is switched back off on exit).

## Decisions taken (change in `config.py`)

- 48 h retention, 50 MB cap. - Text inside text boxes is not read. - Screenshot fallback on. -
  Recording is opt-in per run (`trail start`); it is not yet part of `lmemm.py start`.

## Not done

Feeding the trail into memory items/context; a menu entry; showing it on the pill; Windows; reading
`user.watch_apps` from memory.json; per-site allow/exclude lists beyond `config.SKIP_*`.
