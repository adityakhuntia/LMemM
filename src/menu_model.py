"""LMemM - the menu-bar item, as data. Plain functions, no UI, all tested.

The menu-bar icon answers one question at a glance: is LMemM OK? It follows the pill's
single mark (rules.pill_mark, R8): one mark for whatever is wrong or paused, red only for a
permission that is off. The menu under it says the same thing in words, then lists what
you can do. menubar.py only draws this and forwards clicks; it decides nothing.

    M1  The icon is the pill's capsule. With a mark it wears one badge: red for a permission
        that is off, grey for anything else, and two bars in the grey badge for a pause.
    M2  The first lines of the menu are the status: a short title and one line, the same
        words as the pill's card. Nothing on it is clickable.
    M3  Quit LMemM is always the last row, and always there.
"""

import apps
import rules

RED_MARKS = {"screen_off", "mic_off"}                   # a permission that is off (R8)

WORDS = {
    "screen_off": ("Screen access is off", "LMemM cannot see what you work on."),
    "private": ("Private window", "LMemM is not reading it."),
    "unwatched": ("Not watching this app", "You chose which apps LMemM can see."),
    "mic_off": ("Mic is off", "Voice notes need the microphone. You can still type notes."),
}


def watching_line(watch_apps):
    """"Every app", or "Only Chrome, VS Code +2"."""
    return apps.describe(watch_apps) or "Every app"


def status_words(status, watch_apps=()):
    """(mark, title, line) for the top of the menu."""
    mark = rules.pill_mark(status)
    if mark == "paused":
        view = status.get("pause_view") or {"title": "Paused", "line": ""}
        return mark, view["title"], view["line"]
    if mark:
        return (mark,) + WORDS[mark]
    return None, "LMemM is watching", watching_line(watch_apps)


def icon_spec(mark):
    """What the icon draws besides the capsule: {"badge": None | "red" | "grey", "glyph": None | "pause"}."""
    if not mark:
        return {"badge": None, "glyph": None}
    return {"badge": "red" if mark in RED_MARKS else "grey", "glyph": "pause" if mark == "paused" else None}


QUIT = {"id": "quit", "title": "Quit LMemM", "key": "q"}


def view(status, watch_apps=()):
    """The whole menu-bar item: {"mark", "tone", "title", "line", "icon", "rows"}.
    tone is "ok", "red" or "grey" (the colour of the dot beside the title). rows are the
    clickable lines, top to bottom; {"id": "-"} is a divider."""
    mark, title, line = status_words(status, watch_apps)
    spec = icon_spec(mark)
    return {"mark": mark, "tone": spec["badge"] or "ok", "title": title, "line": line, "icon": spec,
            "rows": [QUIT]}


def signature(v):
    """A short string that changes only when the menu would look different, so it is rebuilt
    only then (an open menu never flickers)."""
    return repr((v["title"], v["line"], v["icon"]["badge"], v["icon"]["glyph"], tuple((r["id"], r.get("title")) for r in v["rows"])))
