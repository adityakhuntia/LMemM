"""LMemM - what LMemM proposes and you decide, as plain functions. No UI, all tested.

Two kinds of proposal wait in a small list until you answer them:

    a project     "These 3 things look like one project": Create it, or Dismiss.
    for a project "These 2 things may belong in Q3 plan": Add them, or say Not here.

    S1  Nothing is ever filed without an answer. A proposal only waits; the pill and the window both
        show it, and answering it in either place clears it in both.
    S2  "Dismiss" and "Not here" are permanent (R14): the same proposal never comes back. Dismissing a
        project remembers its name on each thing; Not here keeps the thing out of that project.
    S3  A proposal never offers what makes no sense: fewer than two things for a new project, a thing
        already in the project, a thing kept out of it, a thing that is gone, an archived project.
        The list tidies itself every time it is read.
    S4  Answers are the same actions as everything else in the window: one sentence, and Undo.
    S5  Where proposals come from is a separate matter. `lmemm.py suggest` and `suggest-for` stand in
        for the model until it exists; this file only holds, tidies and answers them.
"""

import notes
import page_model
import projects

ACTIONS = ("accept_project", "dismiss_project", "accept_items", "reject_items")
FOR_PROJECT_MIN, NEW_PROJECT_MIN = 1, 2


def empty():
    return {"version": 1, "n": 0, "projects": [], "items": []}


def _next(sug):
    sug["n"] = sug.get("n", 0) + 1
    return f"s{sug['n']}"


def offer_project(sug, items, name, ids, reason=""):
    """Add "make these a project". Returns the entry, or None when it makes no sense (S3)."""
    name = projects.clean(name) or "Project"
    ids = [i for i in dict.fromkeys(ids) if i in items]
    if len(ids) < NEW_PROJECT_MIN or notes.was_declined(items, ids, name):
        return None
    for e in sug["projects"]:
        if projects.key(e["name"]) == projects.key(name) or set(e["ids"]) == set(ids):
            return e
    entry = {"id": _next(sug), "name": name, "ids": ids, "reason": reason or "Opened together"}
    sug["projects"].append(entry)
    return entry


def offer_items(sug, reg, items, pid, ids, reason=""):
    """Add "these may belong in `pid`". Returns the entry, or None when none of them can (S3).
    ValueError says it when the project is not there."""
    projects.get(reg, pid)
    if projects.hidden(reg, pid):
        return None
    ok = [i for i in dict.fromkeys(ids) if i in items and projects.allowed(items[i], pid) and pid not in projects._members_of(items[i])]
    if len(ok) < FOR_PROJECT_MIN:
        return None
    for e in sug["items"]:
        if e["pid"] == pid:
            e["ids"] = list(dict.fromkeys(e["ids"] + ok))
            return e
    entry = {"id": _next(sug), "pid": pid, "ids": ok, "reason": reason or "Looks like it belongs here"}
    sug["items"].append(entry)
    return entry


def tidy(sug, reg, items):
    """Drop what no longer makes sense (S3). Returns True when anything changed."""
    before = repr(sug)
    keep = []
    for e in sug["projects"]:
        e["ids"] = [i for i in e["ids"] if i in items]
        if len(e["ids"]) >= NEW_PROJECT_MIN and not notes.was_declined(items, e["ids"], e["name"]):
            keep.append(e)
    sug["projects"] = keep
    keep = []
    for e in sug["items"]:
        if not projects.exists(reg, e["pid"]) or projects.hidden(reg, e["pid"]):
            continue
        e["ids"] = [i for i in e["ids"] if i in items and projects.allowed(items[i], e["pid"])
                    and e["pid"] not in projects._members_of(items[i])]
        if len(e["ids"]) >= FOR_PROJECT_MIN:
            keep.append(e)
    sug["items"] = keep
    return repr(sug) != before


def _thing(reg, item, now, here=None):
    return page_model._thing(reg, item, now, here=here)


def view(sug, reg, items, now):
    """Everything the window and the pill read, tidied (S3):
    {"count", "projects": [{id, name, reason, things}], "items": [{id, pid, name, reason, things}]}."""
    tidy(sug, reg, items)
    return {"count": len(sug["projects"]) + len(sug["items"]),
            "projects": [{"id": e["id"], "name": e["name"], "reason": e["reason"],
                          "things": [_thing(reg, items[i], now) for i in e["ids"]]} for e in sug["projects"]],
            "items": [{"id": e["id"], "pid": e["pid"], "name": projects.get(reg, e["pid"])["name"], "hue": page_model.hue(e["pid"]),
                       "path": " › ".join(projects.path_names(reg, e["pid"])), "reason": e["reason"],
                       "things": [_thing(reg, items[i], now, here=e["pid"]) for i in e["ids"]]} for e in sug["items"]]}


def drop_ids(sug, ids):
    """The pill answered for these things (it files by name): clear every proposal that is now settled."""
    gone = set(ids)
    sug["projects"] = [e for e in sug["projects"] if not gone & set(e["ids"])]
    for e in sug["items"]:
        e["ids"] = [i for i in e["ids"] if i not in gone]
    sug["items"] = [e for e in sug["items"] if e["ids"]]


# ---------------------------------------------------------------- answering (S1, S2, S4)

def _entry(sug, kind, sid):
    for e in sug[kind]:
        if e["id"] == sid:
            return e
    raise ValueError("That suggestion is gone already. Nothing was changed.")


def _some(entry, ids):
    """The things being answered: all of them, or the chosen ones that are still in the proposal."""
    chosen = entry["ids"] if not ids else [i for i in ids if i in entry["ids"]]
    if not chosen:
        raise ValueError("That suggestion is gone already. Nothing was changed.")
    return chosen


def _settle(sug, kind, entry, chosen):
    entry["ids"] = [i for i in entry["ids"] if i not in chosen]
    if not entry["ids"]:
        sug[kind].remove(entry)


def run(reg, items, sug, action, sid=None, ids=(), name=None):
    """Answer one proposal. Returns {"message", "go"} (and "stay" when the page does not change)."""
    if action in ("accept_project", "dismiss_project"):
        entry = _entry(sug, "projects", sid)
        name = projects.clean(name) or entry["name"]
        if action == "accept_project":
            pid = projects.find(reg, name, any_depth=True) or projects.create(reg, name)
            moved = projects.move_to(reg, items, entry["ids"], pid)
            sug["projects"].remove(entry)
            return {"message": f"Made “{projects.get(reg, pid)['name']}” · {page_model.plural(len(moved), 'thing')}", "go": pid}
        for iid in entry["ids"]:
            declined = items[iid].setdefault("declined_projects", []) if iid in items else []
            if entry["name"] not in declined:
                declined.append(entry["name"])
        sug["projects"].remove(entry)
        return {"message": f"Won't suggest “{entry['name']}” again", "go": None, "stay": True}
    if action in ("accept_items", "reject_items"):
        entry = _entry(sug, "items", sid)
        pid = entry["pid"]
        place = projects.get(reg, pid)["name"]
        chosen = [i for i in _some(entry, ids) if i in items]
        what = f"“{page_model.title_of(items[chosen[0]])}”" if len(chosen) == 1 else page_model.plural(len(chosen), "thing")
        if action == "accept_items":
            projects.add_also(reg, items, chosen, pid)
            message = f"Added {what} to “{place}”"
        else:
            projects.not_this(reg, items, chosen, pid)
            message = f"{what[0].upper() + what[1:]} won't be suggested for “{place}” again"
        _settle(sug, "items", entry, chosen)
        return {"message": message, "go": None, "stay": True}
    raise ValueError("That is not something a suggestion can do.")
