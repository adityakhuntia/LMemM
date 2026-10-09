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
