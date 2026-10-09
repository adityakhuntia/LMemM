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
    R10 Finishing a note follows FinishFlow (below) and the table in the Finished Notes mock-up:
        one tap flips a note; a finished note holds 1.2 s then folds; the pill counts open notes
        at once; "All caught up" shows once per clear, only after the last fold, and still lets
        you add a note; Undo reverts a batch of ticks made within 2 s.
    R11 An app you did not choose in setup ("only some apps") is never captured, read or
        remembered. The pill wears one neutral mark there (not red: nothing is wrong), its card
        says LMemM is not watching this app, and ⌃⌥N opens that card instead of failing quietly.
        Marks, strongest first: paused, screen access off, private window, app not chosen,
        mic off (see R8).
    R12-R15 are about projects and live in projects.py (tested in test_project_tree.py):
        R12 any depth, never a loop, no two with one name in one place; R13 a thing has one main
        project and may be "also in" others, and counts use the main one; R14 "Not this
        project" is permanent for suggestions; R15 archive, delete and merge lose nothing by
        accident (merge keeps the old name as an alias).
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
    if status.get("unwatched"):
        return "unwatched"
    if status.get("mic_off") and not count and not has_suggestion:
        return "mic_off"
    return None


def empty_kind(view):
    """"fresh" (no notes at all here), "caught" (every note done), or None. `view` is
    notes.card_view() in the "here" mode."""
    if not view or view.get("empty") or view.get("mode") != "here" or view["rows"] or view["more"]:
        return None
    return "caught" if view.get("done_here") else "fresh"


def pill_state(note_open, saved, hover, card_open, count, has_suggestion, mark=None, empty=None, cleared=False):
    """Which look the pill has. The first rule that applies wins."""
    if note_open:
        return "rest"
    if saved:
        return "saved"
    if mark:
        return mark
    if cleared:
        return "cleared"
    if empty and (hover or card_open):
        return empty
    if hover and not card_open:
        return "peek"
    if count:
        return "count"
    return "suggest" if has_suggestion else "rest"


def hotkey_action(note_open, card_open, paused, unwatched=False):
    """What ⌃⌥N does right now: ignore, show_paused, show_unwatched (R11), open_note, or
    close_card_then_open_note."""
    if note_open:
        return "ignore"
    if paused:
        return "show_paused"
    if unwatched:
        return "show_unwatched"
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


# ---------------------------------------------------------------- finishing notes (R10)

class FinishFlow:
    """What the card does around ticking, as plain state with a clock passed in. Persisting the
    tick is the caller's job; this only decides how long a finished note stays on screen, what
    Undo reverts, and when "All caught up" shows. `open_left` is the number of open notes
    across the project after the change."""

    HOLD = 1.2           # a finished note stays on screen, crossed out
    FOLD = 0.38          # then fades away
    BATCH = 2.0          # ticks this close together are one batch (one Undo)
    TOAST = 6.0          # how long "Marked done · Undo" stays
    REOPENED = 1.8

    def __init__(self):
        self.at = {}                 # note id -> when it was finished (while still on screen)
        self.batch = []              # note ids finished within BATCH of each other
        self.last = 0.0
        self.toast_until = 0.0
        self.undoable = True
        self.armed = False           # the last open note was just finished: celebrate when folds end

    def tick(self, nid, now, open_left):
        """Finish a note. Returns nothing; the caller has already saved it."""
        if now - self.last > self.BATCH:
            self.batch = []
        self.last = now
        self.batch.append(nid)
        self.at[nid] = now
        self.toast_until, self.undoable = now + self.TOAST, True
        self.armed = open_left == 0

    def phase(self, nid, now):
        """None (not on screen), "hold" (crossed out, tappable) or "fold" (fading, not tappable)."""
        at = self.at.get(nid)
        if at is None:
            return None
        age = now - at
        if age < self.HOLD:
            return "hold"
        if age < self.HOLD + self.FOLD:
            return "fold"
        del self.at[nid]
        return None

    def holding(self, now):
        return [nid for nid in list(self.at) if self.phase(nid, now)]

    def cancel(self, nid, open_left):
        """Tapping a finished note during its hold reopens it; the clear is cancelled."""
        self.at.pop(nid, None)
        self.batch = [i for i in self.batch if i != nid]
        if open_left > 0:
            self.armed = False
        if not self.batch:
            self.toast_until = 0.0

    def undo(self, open_left):
        """Revert the whole batch. Returns the ids to reopen."""
        ids, self.batch = self.batch, []
        for nid in ids:
            self.at.pop(nid, None)
        self.toast_until = 0.0
        if open_left + len(ids) > 0:
            self.armed = False
        return ids

    def reopened(self, now):
        self.toast_until, self.undoable, self.batch = now + self.REOPENED, False, []

    def toast(self, now):
        """(text, undoable) while the line at the bottom shows, else None."""
        if now >= self.toast_until:
            return None
        if not self.undoable:
            return "Reopened", False
        n = len(self.batch)
        return ("Marked done" if n <= 1 else f"{n} marked done"), True

    def close_card(self):
        """Closing the card ends the Undo window. Holds carry on; Done keeps everything."""
        self.batch, self.toast_until = [], 0.0

    def update(self, open_left, now):
        """Call often. Returns "clear" exactly once per clear, when the last fold has ended."""
        if open_left > 0:
            self.armed = False
        if self.armed and not self.holding(now) and open_left == 0:
            self.armed = False
            return "clear"
        return None

    def signature(self, now):
        """Changes whenever what the card shows around ticking would change."""
        return (tuple(sorted((n, self.phase(n, now)) for n in list(self.at))), self.toast(now))
