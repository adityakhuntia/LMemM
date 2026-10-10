"""LMemM - the window, as data. Plain functions, no UI, all tested.

The window opens with one question answered at the top: what state is LMemM in? The rest of
the window (projects, notes) arrives in later steps; this file only decides the banner.
window.py draws it and forwards the button press; it decides nothing.

    W1  One banner, always at the top of the window, saying the single strongest state. Never
        two. No banner at all means all is well, and the window says what it is watching.
    W2  Strongest first: damaged memory file, loading, first run, then the pill's own mark
        (rules.pill_mark, R8: paused, screen access off, private window, app not chosen, mic off).
    W3  The words are the menu's and the pill's words (menu_model.status_words); only the
        states the pill never has (damaged file, loading, first run) are new here.
    W4  At most one button, and only when there is one clear thing to do: Resume, Restart,
        Open System Settings, Finish setup, Show the file. A state with nothing to do has none.
    W5  Red only for a permission that is off, or a memory file that cannot be read. A pause,
        a private window, an app you did not choose are grey. Loading and first run are calm.
    W6  Every button is an id the menu already knows (resume, restart, access, setup), so the
        window and the menu can never disagree about what a press does. "show_file" is the one
        new id.
"""

import menu_model

MEMORY_OK, MEMORY_LOADING, MEMORY_FIRST_RUN, MEMORY_DAMAGED = "ok", "loading", "first_run", "damaged"

# what a press does for a state: (button title, row id). None = nothing to do.
ACTIONS = {
    "paused:manual": ("Resume", "resume"),
    "screen_off": ("Open System Settings", "access"),
    "restart": ("Restart LMemM", "restart"),
    "mic_off": ("Open System Settings", "access"),
    "first_run": ("Finish setup", "setup"),
    "damaged": ("Show the file", "show_file"),
}

STATE_WORDS = {
    MEMORY_LOADING: ("Getting your memory ready", "This takes a moment."),
    MEMORY_FIRST_RUN: ("Setup is not finished", "LMemM will start remembering once you finish."),
    MEMORY_DAMAGED: ("LMemM cannot read its memory", "Nothing was changed. Your memory file may be damaged."),
}


def banner(status, memory=MEMORY_OK, watch_apps=()):
    """{"kind", "tone", "title", "line", "button"} or None when all is well.
    tone is "red", "grey" or "calm"; button is {"title", "id"} or None."""
    if memory in STATE_WORDS:
        title, line = STATE_WORDS[memory]
        tone = "red" if memory == MEMORY_DAMAGED else "calm"
        return _banner(memory, tone, title, line, ACTIONS.get(memory))
    mark, title, line = menu_model.status_words(status, watch_apps)
    if not mark:
        return None
    key = "restart" if mark == "screen_off" and status.get("restart") else mark
    if mark == "paused":
        key = "paused:" + (status.get("paused") or "")
    tone = "red" if mark in menu_model.RED_MARKS and key != "restart" else "grey"
    return _banner(key, tone, title, line, ACTIONS.get(key))


def _banner(kind, tone, title, line, action):
    return {"kind": kind, "tone": tone, "title": title, "line": line,
            "button": {"title": action[0], "id": action[1]} if action else None}


def view(status, memory=MEMORY_OK, watch_apps=()):
    """The whole window: {"banner", "heading", "line"}. heading and line are the quiet
    answer shown when there is no banner, and under it otherwise."""
    return {"banner": banner(status, memory, watch_apps),
            "heading": "LMemM",
            "line": "Watching: " + menu_model.watching_line(watch_apps)
                    if memory == MEMORY_OK else ""}


def signature(v):
    """Changes only when the window would look different, so it is rebuilt only then."""
    b = v["banner"]
    return repr((v["heading"], v["line"], b and (b["kind"], b["tone"], b["title"], b["line"], b["button"] and b["button"]["title"])))
