# LMemM — Large Memory Model (prototype)

Watches what you do on your Mac and keeps a small memory of it: which app you
were in, what you were doing there, and what it was about. One entry per thing
(an email draft, a document, a chat, a file), updated when you come back to it.
Capture, OCR, activity rules and speech recognition run locally on your Mac.
You can also opt into a timestamped keyboard/cursor timeline for VS Code,
linked to screenshots and memories. No external model or backend is used.

## Setup (once)

macOS only. Needs Python 3 with PyObjC. From the repository root:

```bash
cd LMemM
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Grant your terminal app (Terminal, iTerm, VS Code, ...) these permissions in
**System Settings → Privacy & Security**, then quit and reopen it:

- **Screen Recording**: needed for screenshots and window titles.
- **Automation**: macOS asks the first time it reads a browser's URL. Allow it.
- **Input Monitoring** and **Accessibility**: only needed for the opt-in input
  timeline below. Enable the app launching Python, then fully quit and reopen it.

The speech helper needs clang/Xcode Command Line Tools to build. Microphone and
Speech Recognition permissions are requested when you try voice notes; typed
notes remain available without speech. Restart a running tracker after upgrading
code or dependencies. Run only one tracker at a time.

## Use

```bash
python3 lmemm.py             # start; Ctrl-C to stop
python3 lmemm.py memory      # see what was remembered
python3 lmemm.py memory 5 --content  # inspect excerpts and explicit decision quotes
python3 lmemm.py memory 20 --events  # inspect the latest input timeline
python3 lmemm.py status      # current recording/pause state
python3 lmemm.py pause       # pause screenshots and input; cancel an open note
python3 lmemm.py resume      # resume; retry an unavailable/disabled input listener
python3 lmemm.py pin         # (in another terminal) force-save the current screen
python3 lmemm.py note        # same as ⌃⌥N: dictate a note onto what you're on
```

While it runs it prints one line each time what you're doing changes:

```
22:16:23  timer        Gmail      Looking through the inbox (1,792 unread)
22:16:28  timer        Gmail      Writing an email to Aditya Gupta (gmail.com) (no subject yet)
22:16:52  app_switch   VS Code    Editing lmemm.py in LMemM   (back to it)
```

To run capture-only in the background instead (input stays off by default):

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

## Keyboard and cursor timeline (opt-in)

Normal startup watches screens without starting an input listener. To enable the
first collector:

```bash
python3 lmemm.py --input-events --input-app com.microsoft.VSCode
# Optional: --input-retention-hours 4
```

Enable **Input Monitoring** and **Accessibility** for the launching app in macOS
Settings, then quit/reopen it. Input currently supports **VS Code only**; browser
documents and other apps are excluded from detailed input collection.

The listener records timestamped keyboard **bursts and counts**, coarse 3×3
cursor movement/drag regions, clicks and scroll buckets. Summaries link to an
older before-image (with its age), a settled after-image, and the memory item
resolved by OCR. Keyboard activity alone is not proof of authored text or intent.

```bash
python3 lmemm.py status
python3 lmemm.py memory 20 --events --content
python3 lmemm.py pause
python3 lmemm.py resume
```

Pause stops screenshot capture too and cancels an open note panel. Commands
request a PID-scoped change; `status` shows acknowledgement. Resume retries a
disabled/unavailable collector with fresh permission checks. Missing permission,
secure or uncertain focus, delayed input and listener failures produce visible
coverage gaps rather than being assigned to another app.

VS Code's Electron accessibility tree may be disabled even after permission is
granted. The collector enables its documented `AXManualAccessibility` flag only
for foreground allowed VS Code, and restores flags it changed on normal stop.
This can add processing cost; a crash may leave it enabled until VS Code quits.
Test inside an **editor file**, not the integrated terminal: unverified text-field
subroles remain blocked. Listener startup saying “recording” does not prove that
accepted events are flowing—inspect the event timeline.

### Tab and app shortcuts

| Shortcut | Recorded evidence |
|---|---|
| **Ctrl+Tab** | forward tab-switch step |
| **Ctrl+Shift+Tab** | backward tab-switch step |
| **Cmd+Tab** | forward app-switch step |
| **Cmd+Shift+Tab** | backward app-switch step |

Each accepted Tab key-down contributes one classified step. `memory --events`
shows forward/backward totals and source-matched observed context changes or
departures. Confirmation does not cross pause/security gaps or overwrite an
earlier result. A shortcut is evidence of a requested action, not proof that a
specific tab/window was selected; VS Code bindings can change its behavior.

Counts cover accepted permitted focus. macOS's app switcher can own focus or
event targets, so repeated Cmd+Tab events may be omitted. **Step count is not a
reliable count of windows passed.** Cmd+Tab switches apps; their order and windows
are not yet modeled. Browser tab identity and reliable window-close semantics
remain future work.

Characters, clipboard and editable accessibility values are never read by the
input collector. Only the requested shortcut families transiently inspect
modifiers and Tab identity; raw keycodes/modifiers are never stored. Other
keyboard input remains counts, not a key journal.

## When it takes a screenshot

- When you switch apps, tabs or windows (after waiting ~1s for the screen to settle)
- Every 5s while you stay on the same window (`python3 lmemm.py --every 10` to change)
- Pauses for idle/lock/sleep and manual pause; a pin can wake an idle capture
- Skips configured password managers, private/incognito windows, and banking,
  payment and login pages using foreground checks (lists in `tracker.py`)
- With input enabled, accepted clicks, completed keyboard/scroll bursts and
  navigation shortcuts request a capture through the same debounce; movement
  alone does not. Ordinary captures have a 2s minimum gap and a periodic fallback.

These are foreground filters, not a guarantee that an entire display contains no
sensitive content. See the privacy limits below.

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
These are heuristic labels: loading, animation and program output can resemble
received text, and the tracker's own terminal output can contaminate activity.
Observed text is not proof that you authored it.

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
- `data/<ts>.jpg` and `.json`: ordinary retained screenshots and capture/OCR
  metadata. Older item screenshots are replaced; redundant frames are removed.
- `data/memory/inputs/<session>.json`: detailed input summaries, status/gaps,
  loss counters and capture/item links.
- `data/memory/inputs/frames/<session>/`: retained source images for input links.
- `data/memory/contributions/`: a pre-feature baseline and session-owned
  evidence for rebuilding shared memories after session deletion.

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

## Privacy and retention

Input observation is listen-only: it does not suppress, modify or synthesize your
input. Permission, secure-focus, context-boundary and target-process checks gate
detail collection. Event time is calibrated to the session's monotonic clock;
native ordering is separate from polling/gap time. Truly delayed events still
produce a gap at the 100ms guard instead of being attributed to new focus.

Detailed input is bounded to 30s of transient context and at most 24h on disk
(configurable shorter), with a 4,096-event cap and visible expiry/capacity-loss
counters. Startup, periodic maintenance and inactive event inspection prune all
sessions. While stopped, expiry is enforced on the next startup/read; there is no
separate background deletion scheduler. Ordinary memories, notes, excerpts and
contribution evidence have longer-lived retention.

New input/control/provenance files and input source-image copies use private
permissions, but **JSON/JPEG storage remains plaintext**. No encryption or
screenshot redaction has been added. Ordinary capture still saves whole displays
and samples pointer positions; the input allowlist does not scope screenshots.
Overlapping/background windows, imperfect foreground geometry, OCR, titles and
URLs can expose sensitive content even without a key journal. Cropping/masking,
stronger capture controls and encryption remain work to do.

## Delete a session

Stop tracking, then inspect the plan before deleting:

```bash
python3 lmemm.py delete-session SESSION --dry-run
python3 lmemm.py delete-session SESSION --confirm SESSION
```

The confirmation must match the exact session ID. Deletion rebuilds shared items
from the legacy baseline and surviving session-owned contributions, removes owned
input/capture/session evidence, and recovers interrupted operations on the next
memory load.

It blocks active tracking, legacy sessions without reconstructable provenance,
referenced replay copies, external memory changes, and source screenshots still
needed by retained evidence. These blockers preserve unrelated work; deletion
does not guess at missing ownership. Try it on disposable test data first.

## Files

| File | What it does |
|---|---|
| `lmemm.py` | start, memory/content/events, notes/pins, pause/resume/status and deletion |
| `tracker.py` | watches macOS for app / tab / window changes, takes screenshots, keeps the memory |
| `resolver.py` | reads each screenshot: text + layout (Apple Vision, on-device) |
| `dictation.py` | the ⌃⌥N hotkey, the note window, and the speech helper it starts |
| `listen/` | the speech helper's source (Objective-C) and its Info.plist |
| `activity.py` | compares each screenshot with the last one: changed regions, scrolling, typing / reading / receiving / focus |
| `understand.py` | rules that turn a screen into "what you're doing" (Gmail, chats, AI apps, editors, browser, ...) |
| `memory_content.py` | foreground text extraction, bounded excerpt history, explicit decision quotes |
| `input_events.py` | bounded interaction summaries, native event ordering and context boundaries |
| `input_monitor.py` | listen-only native adapter, privacy/focus checks and narrow shortcut classification |
| `input_store.py` | retained input/capture links, provenance, pruning and session deletion/recovery |
| `run.sh` | background start / stop |
| `logger.py`, `peek.py` | the earlier fixed-interval logger and its summary (still work on their own) |

## Verify and try it

After upgrading an existing checkout, reinstall requirements and restart the
tracker so it loads the new code. The frameworks include Cocoa, Quartz,
ApplicationServices and Vision. Run the complete suite:

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
```

The integration tests generate their own image and run real on-device OCR; no
personal captures are needed. Run them on macOS with access to graphics services
(a restricted execution sandbox may prevent Vision from running).


The final verified implementation run passed **89 tests**: real Vision OCR,
native local-only speech policy, identity/content/migration, note ownership,
fake-native input/focus/privacy, navigation, retention and deletion recovery.
Automated tests do not start a real input listener or microphone.

Basic input collection/linkage worked in a user-driven VS Code session: 56
accepted presses in six bursts, cursor/click/scroll summaries and 11 summaries
linked to captures/items. That run exposed false ordering gaps, since repaired.
**The latest shortcut and ordering cleanup still needs a live repeat test.**

For a short check, start the opt-in command, edit/scroll/click in a non-sensitive
VS Code file, try the four shortcuts above, switch to an excluded app and back,
pause/resume, open/cancel a note, then Ctrl-C. Inspect `memory 100 --events --content`
and compare accepted steps, gaps and links with your actions. Notes/voice,
Google Docs cross-session identity and longer/multi-display runs need their own
live checks. See [HANDOVER.md](HANDOVER.md) for setup, acceptance criteria, commit
attribution and architecture; [context.md](context.md) holds the development record.

## Next

First validate the latest live input/navigation coverage, then fix foreground
window geometry, screenshot isolation and the tracker's own log contamination.
Strengthen authored-text attribution and stable project/file/browser identities
before widening collection.

The next product layer is evidence-backed project recall: “What did we do here
two days ago, why, and what is left?” That needs explicit notes/tasks/decisions,
retrieval with source links, and a distinction between observation and intent.
A transactional persistent store and scoped retrieval/proposal APIs can then
share permitted context with configured AI agents. Semantic recall, proactive
reminders and universal agent memory are not implemented yet.
