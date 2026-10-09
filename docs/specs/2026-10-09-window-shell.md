# Step 4: the window shell and its state banner

One idea: the window says what state LMemM is in. Rules W1-W6 are in `src/window_model.py` (tested in
`tests/test_window_model.py`); `src/window.py` only draws them. The projects and notes arrive in steps 5 to 6.

Open it from the menu-bar item: **Open LMemM** (first row). Closing it only hides it.

| State | Banner | Colour | Button |
|---|---|---|---|
| All well | none; "Watching: Every app" | | |
| Paused by you | the pill's words | grey | Resume |
| Paused (stepped away) | the pill's words | grey | none |
| Screen access off | Screen access is off | red | Open System Settings |
| Screen on, needs restart | Screen access is on | grey | Restart LMemM |
| Mic off | Mic is off | red | Open System Settings |
| Private window / app not chosen | the pill's words | grey | none |
| Setup not finished | Setup is not finished | calm | Finish setup |
| Getting memory ready | in the model only | calm | none |
| Memory file unreadable | in the model only | red | Show the file |

Not wired yet: "Getting memory ready" and "unreadable file" (LMemM stops at start when the file is damaged, so the window
never sees it), and "not running" (the window lives inside the running app).

# Step 5: the project page (read only)

Rules P1-P8 are in `src/page_model.py` (tests in `tests/test_page_model.py`); `src/window.py` draws them.

- **Sidebar:** search, Needs you (top 3 and "See all"), the project tree (any depth, each level pages itself).
- **Home:** Needs you, then the top-level projects, and how many things are not in a project yet.
- **A project:** breadcrumb, "Pick up where you left off" (things with open notes, newest first), sub-projects,
  then things grouped Today / This week / Earlier with a switch for "Only here" or "With sub-projects" and app filters.
- **Search:** projects (including names left by a merge), things and open notes, across every project.
- Looking never writes to memory or to the tree. The one write: opening the window files things that older
  versions kept only by project name into the tree (`projects.adopt`, safe to repeat).

Known limits, for step 11: creating thousands of projects one by one is slow (each create checks its siblings by
scanning); showing them is fast (50 ms for 10,000). The window is a fixed size.

## Step 5b: a thing's own page, a banner that matches the page

- Any thing or note (a Needs you row, a Pick up card, a row in Things, a search hit) opens its own page: the
  title, the projects it is in, its open notes in full, the finished ones, last seen, time spent, visits and what
  LMemM read from it. Back returns to where you were. Rule P9.
- The banner sits at the top of the page's own column, as a soft box with an icon, its words on the left and its one
  button on the right, in the same style as the cards.
- Scroll bars are always shown, so it is clear what scrolls.

## Step 5c: a project page that scrolls only where it should

- On a project page the top stays put (breadcrumb, title, three small Pick up cards, sub-project chips, the Things
  controls) and only the list of things under it scrolls. The window is 1080 by 720.
- Scroll bars are the thin macOS overlay kind, over the empty edge of the content, never beside it.
- The sidebar has its own soft tint and a hairline between it and the page.
- A thing's page: where it lives, four quiet tiles (last seen, first seen, time spent, visits), each open note in
  its own box, what LMemM noticed, then "What was on screen" as short passages (source and when, any decision found as
  a quote, six lines each with "Show more").

# Step 6: notes in the window

On a thing's page (click any thing or note): tap the circle to tick a note, tap a finished one to reopen it, type in
the bar under the page and press Return to add a note. Ticking follows the pill's rules (R10, `rules.FinishFlow`): the
note stays crossed out for 1.2 s, then moves to Finished; "Marked done · Undo" shows for 6 s and Undo reverts the batch.
The window and the pill read and write the same notes (`notes.set_done`, `notes.record`), so a tick in either shows in
both within a second. Not yet: ticking from the Pick up cards or the Needs you list (open the thing first).

# Step 7: changing projects from the window

Rules A1-A6 are in `src/project_actions.py` (tests in `tests/test_project_actions.py`).

- **Make:** "New project" at the foot of the sidebar and on All projects; "+ Sub-project" on a project.
- **The ⋯ menu on a project:** Rename, Move to… (a search over places it can go, plus the top level), Merge into…, Archive,
  Delete…. Archived projects wait under "Archived · n" at the foot of the sidebar, each with Bring back.
- **Only Merge and Delete ask**, and they say how many things and sub-projects move. Everything else happens at once.
- **Every change says what it did and offers Undo for 8 seconds** ("Merged “Q3 plan” into “Work” · 12 things · Undo").
  Undo puts the tree and each thing's project back; a thing you filed elsewhere since stays where you put it.
- **Deleting a project never deletes remembered things:** they stay, without a project. Forgetting things is not offered here.

### Step 7 follow-up: typing and the Archived folder

- The name field was added to the overlay before the dimmed backdrop and card, so both covered it and clicks never reached it. It is now moved above them every time a dialog is drawn.
- Archiving no longer makes a project vanish. The tree ends with an **Archived** folder (count beside it). Opening it lists the archived projects with Bring back; each can be opened, read, and brought back from its own page. The separate "Archived · n" link under the tree is gone.

## Step 8: Assign

Rules T1–T6 are in `src/thing_actions.py` (tested in `tests/test_thing_actions.py`).

- **A thing's page** has "Move to…" and "⋯" beside its title, and a "Why it is here" section that only states what is stored (main project, also in, kept out of). The menu: Move to…, Also in…, Not in “X” (one row per project it is in), Forget this….
- **Select** (project page, beside "Things"): tick several things, then Move to…, Also in…, Not in here, Forget…, or Done. The selection ends when you go to another page.
- **Forget** is the only action that asks first (it removes a thing from memory), says what goes with it, and can be undone from the toast. Everything else just happens with Undo.
- **The pill and the window agree.** The pill used to write only a project's name, so moving a thing from the pill left the tree pointing at the old project. Filing, "take it out" and "not this project" on the pill now go through the project tree (`tracker.in_tree`).
- Capture copes with a thing forgotten mid-session (no more adding time to a thing that is gone).

## Step 9: Suggestions

Rules S1–S5 are in `src/suggestions.py` (tests in `tests/test_suggestions.py`). Proposals wait in `data/memory/suggestions.json` until answered.

- **First page:** a "Suggestions" section. A project proposal is a card ("Make “Trip” a project?", the things it would hold, **Create** / **Dismiss**). A project with things waiting shows one row with **Review**.
- **A project's page:** "Suggested for this project" above its things, one row per thing with **Add** / **Not here**, and **Add all**. Also shown on an empty project.
- **Dismiss and Not here are permanent** (R14); Add and Create are the same actions as in step 8, so each says what it did and offers Undo (which also brings the proposal back).
- **The pill and the window share the list.** Answering in either clears it in both; the pill shows the first project proposal waiting.
- **Stand-ins for the model:** `lmemm.py suggest [NAME] [ID…]` (a project) and `lmemm.py suggest-for PROJECT [ID…]` (things for an existing one; with no ids, the three latest not in it).

## Step 10: Settings

Rules G1–G7 are in `src/settings_model.py` (tests in `tests/test_settings_model.py`). Open it from the gear at the bottom of the sidebar or **Settings…** in the menu-bar item.

- **You:** first name (same rules as setup) and what you mostly work on.
- **Apps:** every app, or only the ones you add. Removing the last one means every app, and the line says so. Takes effect immediately, including for the event trail.
- **Access:** the three permissions read live from macOS with setup's own words and buttons. Red only for a permission that is off.
- **Privacy:** what LMemM never reads (password managers, banks and sign-in pages, private windows, password fields), and apps you add to **Never remember**, skipped before anything is captured or read.
- **General:** keep screenshots 1, 3, 7 or 30 days (the picture goes; the words and notes stay), the note shortcut, and Reopen setup.
- **Data:** where memory lives and how big it is, Show in Finder, and Delete all my data (asks first, as in the menu).
- Every change saves at once, says what it did, and can be undone from the toast. The change is also true in the running app: `Tracker.apply_user` updates the watched apps (and the trail's gate), the never-remember set and the screenshot keep time.
- `tests/window_smoke.py` now also draws all six Settings pages and the app picker.

## Step 11: Polish and scale
- **A real window.** It resizes (minimum 880×560, remembers its size and place), minimises, and the green button makes it full screen. It no longer hides when you go to another app. While it is open LMemM shows in the Dock and ⌘-Tab, so you can come back from any app; closing it returns LMemM to the menu bar only. The page column grows with the window up to 980 wide, then stays centred.
- **Keys.** ⌘K search, ⌘, Settings, ⌘[ Back, ⌘W close, ⌘M minimise, ⌘Q quit, Esc closes a card, then leaves select, then clears search, then goes back. Not in this step: arrow keys and Return to walk the list.
- **VoiceOver.** Every tap area is a button named by its words and can be pressed.
- **Dark mode.** All colours already follow the system; the window background is dynamic.
- **Scale.** `projects.indexed` turns tree and membership lookups into table reads. With 10,000 projects and 50,000 things the first page takes about 0.12 s (was 1.65 s), a project page 0.12 s, search 0.17 s. `tests/test_scale.py` guards it.
- **Narrow.** Chip rows wrap instead of running off the column.

## Step 11 follow-up: walk the lists with the keyboard
- Up/Down move a highlight through the rows of one zone (the sidebar's Needs you and Projects, or the page's things and project cards); Left/Right switch zone; Return opens the highlighted row (while selecting, it ticks it). Esc and ⌘[ still go back. The logic is `keynav.py`; the window only forwards key codes and draws the highlight.
- Keys do nothing while a card is open, and the highlight clears when you move to another page.
- Limit: when a text field (search, the note box) has the keyboard, the arrows belong to it. Press Esc or click the page first.
