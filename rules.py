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
"""


def pill_state(note_open, saved, hover, card_open, count, has_suggestion):
    """Which look the pill has. The first rule that applies wins."""
    if note_open:
        return "rest"
    if saved:
        return "saved"
    if hover and not card_open:
        return "peek"
    if count:
        return "count"
    return "suggest" if has_suggestion else "rest"


def hotkey_action(note_open, card_open, paused):
    """What ⌃⌥N does right now: ignore, open_note, or close_card_then_open_note."""
    if paused or note_open:
        return "ignore"
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
