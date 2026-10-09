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
