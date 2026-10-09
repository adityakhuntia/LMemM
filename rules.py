"""LMemM - the ground rules of the pill, as code. Plain functions, no UI, all tested.

One thing owns the bottom-centre of the screen at a time, in this order:

    1  the note card            (⌃⌥N: you are dictating)
    2  the project card         (you clicked the pill)
    3  the saved confirmation   ("Saved to Q3 plan", about 2 s)
    4  the pill itself          (peek on hover, a count, a suggestion, or at rest)

What that means:

    R1  While the note card is up the pill is dormant (at rest) and clicking it does nothing.
        The note card is never covered, and dictation never stops listening because of a click.
    R2  ⌃⌥N while the project card is open closes that card and opens the note card.
    R3  ⌃⌥N while the note card is already up does nothing (no second card, no restart).
    R4  A note you just saved is on the pill at once, even while its screen is still being read:
        the card never says "No notes here" about the thing you just wrote a note on.
    R5  Opening the project card ends the saved confirmation. Opening anything closes the other.
    R6  Pausing, or a private window, closes the note card without saving.
    R7  Only the note card reacts to Return and Esc.
    R9  Pause is a plain "Pause LMemM" row on the card (never a hidden shortcut), then three
        choices that each show when they end. Any pause, yours or automatic (you stepped away),
        shows the same single pause mark on the pill and nothing else: no count, no words. The card
        says which it is and when it ends; only a pause you chose has a Resume button.
        ⌃⌥N while paused opens that card instead of failing quietly.
    R8  Every state wears a mark on the pill you can read at a glance; the card only confirms it,
        in a title and one line, with at most one thing to do. Red is for a permission that is
        off. A private window and an empty place stay neutral.
        Marks, strongest first: screen access off, private window, mic off (only when nothing
        else is on the pill). On hover or with the card open an empty place, a finished one and
        an empty project picker show their icon too.
"""


def pill_mark(status, count=0, has_suggestion=False):
    """The mark for something wrong here, or None. status: {"screen": bool (allowed),
    "private": bool (this window is not read), "mic_off": bool, "paused": "manual"|"away"|None}."""
    if status.get("paused"):
        return "paused"
    if not status.get("screen", True):
        return "screen_off"
    if status.get("private"):
        return "private"
    if status.get("mic_off") and not count and not has_suggestion:
        return "mic_off"
    return None


def empty_kind(view):
    """"fresh" (no notes at all here), "caught" (every note done), or None. `view` is
    notes.card_view() in the "here" mode."""
    if not view or view.get("empty") or view.get("mode") != "here" or view["rows"] or view["more"]:
        return None
    return "caught" if view.get("done_count") else "fresh"


def pill_state(note_open, saved, hover, card_open, count, has_suggestion, mark=None, empty=None):
    """Which look the pill has. The first rule that applies wins."""
    if note_open:
        return "rest"
    if saved:
        return "saved"
    if mark:
        return mark
    if empty and (hover or card_open):
        return empty
    if hover and not card_open:
        return "peek"
    if count:
        return "count"
    return "suggest" if has_suggestion else "rest"


def hotkey_action(note_open, card_open, paused):
    """What ⌃⌥N does right now: ignore, show_paused, open_note, or close_card_then_open_note."""
    if note_open:
        return "ignore"
    if paused:
        return "show_paused"
    return "close_card_then_open_note" if card_open else "open_note"


def pill_click_action(note_open):
    return "ignore" if note_open else "toggle_card"


def with_pending(card, waiting, blank):
    """The card for the thing in front, plus notes still waiting for their screen to be read
    (waiting: [{"text", "at"}]). They count as notes here, so a note never seems to vanish.
    `blank` builds the empty card when there is none."""
    if not waiting:
        return card
    card = dict(card) if card else blank()
    rows = [{"id": f"pending:{n['at']}", "text": n["text"], "at": n["at"], "on": card["title"],
             "here": True, "done": None, "pending": True} for n in waiting]
    card["left"] = rows + list(card.get("left", []))
    card["plan"] = rows + list(card.get("plan", []))
    return card


# ---------------------------------------------------------------- pausing

PAUSE_CHOICES = ("hour", "tomorrow", "until_resume")
MORNING = 8                                  # "Until tomorrow" ends at 8:00 AM


def pause_end(kind, now):
    """When a pause of this kind ends (a datetime), or None for "until I resume"."""
    from datetime import timedelta
    if kind == "hour":
        return now + timedelta(hours=1)
    if kind == "tomorrow":
        morning = now.replace(hour=MORNING, minute=0, second=0, microsecond=0)
        return morning if now < morning else morning + timedelta(days=1)
    return None


def clock(end, now):
    """"at 3:40 PM", or "tomorrow at 8:00 AM" when it is not today."""
    text = end.strftime("%I:%M %p").lstrip("0")
    return f"at {text}" if end.date() == now.date() else f"tomorrow at {text}"


def pause_options(now):
    """The three choices on the card: what to call them and when each one ends."""
    rows = [("hour", "1 hour"), ("tomorrow", "Until tomorrow"), ("until_resume", "Until I resume")]
    return [{"kind": k, "title": t,
             "sub": f"Back on {clock(pause_end(k, now), now)}" if pause_end(k, now) else "You turn it back on"}
            for k, t in rows]


def paused_view(kind, end, now):
    """The paused card as data. kind: "manual" (you paused) or "away" (you stepped away)."""
    if kind == "away":
        return {"title": "Paused", "line": "You stepped away. Back on as soon as you return.", "resume": False}
    line = ("Nothing is being remembered. Back on " + clock(end, now) + "." if end
            else "Nothing is being remembered until you resume.")
    return {"title": "Paused", "line": line, "resume": True}
