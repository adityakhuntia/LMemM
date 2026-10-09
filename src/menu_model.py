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
    M4  Pause is a plain row, never a hidden shortcut (R9). It opens the same three choices as
        the pill, each saying when it ends. When you paused it, the row is Resume LMemM
        instead. When the pause is automatic (you stepped away) there is nothing to do, so no
        row: the title already says it and LMemM resumes by itself.
"""

from datetime import datetime

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
DIVIDER = {"id": "-"}
PAUSE_PREFIX = "pause:"


def pause_row(now):
    """"Pause LMemM" with the pill's three choices underneath (rules.pause_options)."""
    return {"id": "pause", "title": "Pause LMemM",
            "children": [{"id": PAUSE_PREFIX + o["kind"], "title": o["title"], "detail": o["sub"]}
                         for o in rules.pause_options(now)]}


def pause_kind(row_id):
    """"pause:hour" -> "hour" (one of rules.PAUSE_CHOICES), or None for any other row."""
    if row_id and row_id.startswith(PAUSE_PREFIX) and row_id[len(PAUSE_PREFIX):] in rules.PAUSE_CHOICES:
        return row_id[len(PAUSE_PREFIX):]
    return None


def rows_for(status, now):
    kind = status.get("paused")
    if kind == "manual":
        first = [{"id": "resume", "title": "Resume LMemM"}]
    elif kind:
        first = []
    else:
        first = [pause_row(now)]
    return first + ([DIVIDER] if first else []) + [QUIT]


def view(status, watch_apps=(), now=None):
    """The whole menu-bar item: {"mark", "tone", "title", "line", "icon", "rows"}.
    tone is "ok", "red" or "grey" (the colour of the dot beside the title). rows are the
    clickable lines, top to bottom; {"id": "-"} is a divider."""
    mark, title, line = status_words(status, watch_apps)
    spec = icon_spec(mark)
    now = now or datetime.now()
    return {"mark": mark, "tone": spec["badge"] or "ok", "title": title, "line": line, "icon": spec,
            "rows": rows_for(status, now)}


def signature(v):
    """A short string that changes only when the menu would look different, so it is rebuilt
    only then (an open menu never flickers)."""
    return repr((v["title"], v["line"], v["icon"]["badge"], v["icon"]["glyph"], _rows_sig(v["rows"])))


def _rows_sig(rows):
    return tuple((r["id"], r.get("title"), r.get("detail"), _rows_sig(r.get("children", ()))) for r in rows)
