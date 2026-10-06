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
python3 lmemm.py memory 5 --content  # inspect excerpts and explicit decision quotes
python3 lmemm.py pin         # (in another terminal) force-save the current screen
python3 lmemm.py note        # same as ⌃⌥N: dictate a note onto what you're on
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

## Dictate a note (⌃⌥N)

While it runs, press **⌃⌥N** (Control-Option-N) anywhere. A small window opens
saying what you're on ("Note for: Working on 'Q3 plan'") and it's **already
listening**: just talk, and your words appear as you speak. You can also type
or fix words. **Return** saves, **Esc** cancels, and you're put back in your app.

The note is stored on the memory entry for that doc, email, chat or file,
under `notes`, separately from what LMemM observed:

```json
"notes": [{"at": "2026-10-05T10:12:03", "text": "add a pricing section, ask Rahul for the vendor list",
           "while": "Working on \"Q3 plan\""}]
```

- Speech to text is Apple's on-device recognizer, run by a tiny helper app
  (`listen/listen.m`, built into `bin/LMemM Listen.app` with clang on first run).
  It only runs while the note window is open. The first time, macOS asks you to
  allow **Microphone** and **Speech Recognition** for "LMemM Listen".
- Recognition is required to run on-device. If local recognition or permissions
  are unavailable, type in the same panel; there is no server-recognition fallback.
  Temporary transcript files are removed when the panel closes, including cancel.
- Opening a note first captures and checks the foreground context. If capture is
  blocked or the context changes, no note panel opens for a previous item. Notes
  awaiting OCR are saved to the session immediately and attached after resolution;
  failures leave an explicit unresolved note rather than guessing its owner.
- The hotkey is registered with macOS for that one key combination, so no
  keyboard monitoring and no extra permission.
- `python3 lmemm.py note` opens the same window from a terminal.

## When it takes a screenshot

- When you switch apps, tabs or windows (after waiting ~1s for the screen to settle)
- Every 5s while you stay on the same window (`python3 lmemm.py --every 10` to change)
- Never while idle for 60s+, locked, or asleep
- Never in password managers, private/incognito windows, or banking, payment and login
  pages (lists at the top of `tracker.py`)

## What it notices inside an app

Each screenshot is compared with the previous one of the same thing. Activity
classification uses changed regions alongside three system counters (seconds since
the last key press, scroll and click, never *which* key) and where the pointer
is when the screenshot is taken. That gives one of four activities for each
moment, in any app:

| Activity | Means | Example |
|---|---|---|
| **typing** | you pressed keys and text was edited in place (a line grew, or replaced a placeholder) | writing an email body, a prompt, a doc |
| **reading** | the view scrolled, or nothing changed while you stayed on it | scrolling an article, reading a thread |
| **receiving** | new text appeared with no input from you | a chat message arriving |
| **focus** | you clicked or pointed and that area changed | opening menus, switching panels |

Screens with changes below the pixel-difference threshold reuse previous OCR.
Other captures run OCR on the full screenshot. Text already visible on arrival
is not attributed to a new activity, but can be kept as an observed content
excerpt. Activity rules filter common UI noise such as placeholders and timestamps.

## What you get

Everything goes in `data/`:

- `data/memory/memory.json`: one entry per thing (an email draft, a doc, a chat,
  a file, a page), across all sessions, newest first. Each entry:

  ```json
  {
   "id": "email_draft-69532021",
   "app": "Gmail",
   "what": "Testing Lmemit ?",
   "doing": "Writing an email to Aditya Gupta (gmail.com), subject \"Testing Lmemit ?\"",
   "your_notes": [{"at": "2026-10-05 10:12", "text": "ask Rahul for the vendor list"}],
   "latest": {"to": ["Aditya Gupta (gmail.com)"], "draft": "Hi I am testing the POC ..."},
   "mostly": "typing",
   "activity": {"typing": {"time": "40s", "text": ["Testing Lmemit ?", "Hi I am testing the POC ..."]},
                "reading": {"time": "10s"}},
   "time": {"total": "50s", "visits": 2, "first": "2026-10-05 10:05", "last": "2026-10-05 10:12"},
   "screenshot": "20261005-101203.jpg"
  }
  ```

  Bookkeeping (refs, content hashes, typing areas) is kept out of it, in
  `data/memory/.index.json`.
  New stores use `schema_version: 2`. Legacy full `items` stores migrate on the
  next save; corrupt stores or readable-only stores missing their index stop with
  an error rather than being replaced with empty memory. Keep `.index.json` when
  backing up or moving your memories.
  Observed `content` also retains up to 12 source-attributed excerpts, each
  at most 3,000 characters, and unverified decision quotes.

  **Same thing or a new one?** Google Docs with a document ID in the browser URL
  keep the same memory across sessions, edits, renames and scrolling. Different
  document IDs stay separate even when their titles or visible text match. This
  requires browser URL access; existing duplicate memories are not merged.
  Other contexts use a heuristic based on what you typed:
  if your earlier text is still on screen, it's the same thing (even if its URL
  or title changed while you stayed on it). Otherwise a new name means a new
  thing: two chats in one WhatsApp tab are two entries. If your text vanished while you
  stayed there without scrolling, or you come back and the spot you typed into
  is empty, it's a *new* thing that only looks the same: a second email, a new
  note, a fresh prompt. Chats and threads (anything that received text from
  others) never split.
- `data/memory/sessions/<session>.json`: the timeline of what you were on and when.
  Numeric durations/activity and `item` references remain available alongside
  readable duration strings and `memory` references, including older CLI support.
- `data/<ts>.jpg`: the one screenshot kept per memory entry. Screenshots that
  showed nothing new are deleted.

Content excerpts retain observed text, app/window/URL, and first/last seen times.
Lines outside the foreground window and recognized navigation/control elements
are excluded. Old frames without window geometry still produce activity memories
but no content excerpts. This filtering is heuristic; overlapping windows and
misclassified UI text can still affect the result.

Explicit phrases such as “We chose …” or “Decision: …” are shown as **unverified
decision quotes**. They may be someone else's words on screen; they do not prove
that you made or agreed with a decision. No model infers intent or reasons.
Only visible OCR text is available, not off-screen document content. The CLI
shows the latest three excerpts per item (600-character previews); the JSON
retains the full bounded excerpts. Each quote retains its source text and time,
but older screenshots are still replaced as before.

## Files

| File | What it does |
|---|---|
| `lmemm.py` | the one command: start, `memory`, `pin`, `peek` |
| `tracker.py` | watches macOS for app / tab / window changes, takes screenshots, keeps the memory |
| `resolver.py` | reads each screenshot: text + layout (Apple Vision, on-device) |
| `dictation.py` | the ⌃⌥N hotkey, the note window, and the speech helper it starts |
| `listen/` | the speech helper's source (Objective-C) and its Info.plist |
| `activity.py` | compares each screenshot with the last one: changed regions, scrolling, typing / reading / receiving / focus |
| `understand.py` | rules that turn a screen into "what you're doing" (Gmail, chats, AI apps, editors, browser, ...) |
| `memory_content.py` | foreground text extraction, bounded excerpt history, explicit decision quotes |
| `run.sh` | background start / stop |
| `logger.py`, `peek.py` | the earlier fixed-interval logger and its summary (still work on their own) |

## Verify the resolver

The resolver uses the PyObjC Vision framework bindings included in
`requirements.txt`. After upgrading an existing checkout, reinstall requirements
and restart any running tracker so it loads the updated code:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

The integration tests generate their own image and run real on-device OCR; no
personal captures are needed. Run them on macOS with access to graphics services
(a restricted execution sandbox may prevent Vision from running).

## Opt-in keyboard and cursor timeline

Normal startup remains capture-only. To enable the first input collector:

```bash
.venv/bin/python lmemm.py --input-events --input-app com.microsoft.VSCode
# Optional: --input-retention-hours 4
```

Grant Input Monitoring and Accessibility to the launching app in macOS System
Settings, then restart if requested. The initial input allowlist supports **VS
Code only**; browser input is excluded. Missing permission or uncertain protected
focus produces a visible gap and keeps ordinary capture available.

```bash
.venv/bin/python lmemm.py status
.venv/bin/python lmemm.py pause
.venv/bin/python lmemm.py resume
.venv/bin/python lmemm.py memory 20 --events --content
```

Pause also stops screenshots and cancels an open note panel. Commands request a
PID-scoped state change; `status` shows acknowledgement. A disabled listener can
be retried with `resume`, which checks permissions again.

The collector stores timestamped keyboard **counts**, coarse 3×3 cursor regions,
click categories, scroll buckets and verified allowed-window transitions. It
never reads characters, clipboard or editable AX values. The explicitly requested
Ctrl+Tab/Cmd+Tab shortcut classifier transiently checks modifiers and Tab identity;
no raw keycodes or modifiers are stored.
Keyboard activity is not proof of authored text, Cmd-Tab, a closed window or a
specific tab action. Target-process metadata and context timestamps reject
ambiguous attribution; missing target metadata also causes a gap. See [Apple's
event target process field](https://developer.apple.com/documentation/coregraphics/cgeventfield/eventtargetunixprocessid).

Input summaries link to before/after capture IDs and, after OCR, memory items.
Before-image age is explicit. Movement alone does not trigger screenshots;
clicks and completed keyboard/scroll bursts use existing capture debounce.

Detailed input is bounded to 30 seconds in RAM and at most 24 hours on disk
(configurable shorter), with a 4,096-record disk cap and visible loss counters.
Startup, periodic maintenance and inactive event inspection prune all sessions.
When LMemM is stopped, expiration is enforced on the next startup/inspection;
there is no background deletion scheduler. Input JSON and retained source copies
use private permissions, but remain **plaintext**. The existing capture pipeline
still saves whole-display images and samples pointer positions; input allowlisting
does not limit ordinary screenshot capture. Foreground geometry, overlapping
windows and screenshot redaction remain work to do. Retained input source images
use the input retention limit; ordinary memories/notes retain their existing policy.

After stopping the tracker, inspect a session deletion plan before deleting:

```bash
.venv/bin/python lmemm.py delete-session SESSION --dry-run
.venv/bin/python lmemm.py delete-session SESSION --confirm SESSION
```

Deletion reconstructs shared items from an immutable legacy baseline and surviving
session-owned contributions, removes owned input/capture/session evidence, and
recovers interrupted operations. It blocks legacy sessions without provenance,
active tracking, replay references, external memory changes, and source images
still needed by retained evidence. No live session has been deleted during tests.

Automated coverage includes fake native events, privacy/context boundaries,
retention, deletion/recovery, and existing native OCR/speech-policy checks. Live
VS Code input coverage and permission behavior still need the scripted check in
`context.md`; automated tests install no real global input listener.

VS Code may need its Electron accessibility tree enabled even after macOS grants
permission. The opt-in collector now requests the documented `AXManualAccessibility`
flag for foreground VS Code and restores flags it changed on normal stop. This can
increase Electron's processing cost. Unknown focus and unverified text-field
subroles still cause gaps; test typing in an **editor file**, not the integrated
terminal. Specific rejection reasons are available through `status` and event gaps.
Listener startup alone does not establish successful event collection.

### Navigation shortcut evidence

Ctrl+Tab / Ctrl+Shift+Tab records forward/backward **tab-switch steps**;
Cmd+Tab / Cmd+Shift+Tab records forward/backward **app-switch steps**. Each accepted
Tab key-down contributes one classified step. `memory --events` shows counts by
action/direction and related observed allowed-context changes or departures.
Shortcuts remain evidence of a requested action, not proof a tab/window changed.
Correlation never crosses a pause/security gap or replaces an earlier confirmation.

Counts cover accepted input from permitted VS Code focus only. The macOS switcher
can own focus or event targets, so held/repeated Cmd+Tab events may be omitted.
Counts are not a reliable distance through a list of windows; Cmd+Tab switches apps,
and layouts, ordering, reverse steps and custom keybindings vary. No browser input
or unrestricted key logging was added. Validate these shortcuts with a live run.

Ordering now compares native events against the previous native event, separately
from polling/gap timestamps. This removes false `out_of_order` rejection after a
gap. Truly delayed events still produce visible gaps; the 100ms privacy guard has
not been relaxed just to increase recorded counts.
