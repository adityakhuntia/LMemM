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
