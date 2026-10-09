"""LMemM - putting things in projects from the window, as plain functions. No UI, all tested.

Step 7 shaped the project tree; this is the other half: where each thing lives. A thing has one
main project and may be "also in" others (R13). The window can do five things with one thing or a
handful selected together, and every one goes through project_actions.do so it can be undone.

    T1  Move to: the chosen project becomes the main one. Also in: it joins without leaving.
        Both are picked from live projects only, never one it is already in.
    T2  Not in a project takes it out and keeps it from being suggested back there for good (R14).
        Nothing is lost: the thing stays in LMemM.
    T3  Forget is the one thing that removes a thing from memory. It asks first, says what goes
        with it (its open notes), and can still be undone from the toast. It never touches
        projects.
    T4  "Why it is here" only says what is stored: the main project, the others, the places it is
        kept out of. It never claims a reason LMemM did not record.
    T6  The pill and the window agree: what the pill files, takes out or refuses by name goes
        through the same project tree (file_by_name, unfile_main, decline_by_name).
    T5  Every error is a sentence a person can act on; a thing that is gone since the page was
        drawn is skipped, and if none is left the person is told so.
"""

import notes
import page_model
import projects

ACTIONS = ("assign", "also", "not_this", "forget")
PLACES_SHOWN = 40


def _found(items, ids):
    found = [items[i] for i in ids if i in items]
    if not found:
        raise ValueError("That is gone already. Nothing was changed.")
    return found


def _what(found):
    return f"“{page_model.title_of(found[0])}”" if len(found) == 1 else page_model.plural(len(found), "thing")


def run(reg, items, action, ids=(), pid=None, here=None):
    """Do one thing-action. Returns {"message", "go", "stay": True}: the toast sentence, and no
    change of page. `here` is the project the person is looking at (for Not in here)."""
    found = _found(items, ids)
    mine = [i["id"] for i in found]
    what = _what(found)
    if action == "assign":
        name = projects.get(reg, pid)["name"]
        projects.move_to(reg, items, mine, pid)
        return {"message": f"Moved {what} to “{name}”", "go": None, "stay": True}
    if action == "also":
        name = projects.get(reg, pid)["name"]
        projects.add_also(reg, items, mine, pid)
        return {"message": f"Added {what} to “{name}”", "go": None, "stay": True}
    if action == "not_this":
        name = projects.get(reg, pid)["name"]
        projects.not_this(reg, items, mine, pid)
        return {"message": f"Took {what} out of “{name}”. It won't be suggested there again", "go": None, "stay": True}
    if action == "forget":
        for i in mine:
            del items[i]
        return {"message": f"Forgot {what}", "go": None, "stay": True}
    raise ValueError("That is not something a thing can do.")


def plan_forget(items, ids):
    """{"title", "text", "button"} for the question before Forget (T3)."""
    found = _found(items, ids)
    open_notes = sum(len(notes.open_notes(i)) for i in found)
    extra = f" and its {page_model.plural(open_notes, 'open note')}" if open_notes and len(found) == 1 else \
            f" and {page_model.plural(open_notes, 'open note')}" if open_notes else ""
    it = "it" if len(found) == 1 else "them"
    return {"title": f"Forget {_what(found)}?",
            "text": f"LMemM stops remembering {_what(found)}{extra}. If you open {it} again, {it} can be remembered anew. "
                    "Projects are not touched. You can undo this for a few seconds.",
            "button": "Forget"}


def places(reg, items, ids, kind, query=""):
    """Projects the selected things can go to ("assign": their new main, "also": one more), for the
    picker: {"rows": [{"id", "name", "path"}], "more": n}. Never a place all of them are in (T1)."""
    found = [items[i] for i in ids if i in items]
    want = page_model.fold(query)
    rows = []
    for p, row in reg["projects"].items():
        if projects.hidden(reg, p):
            continue
        if found and all((projects._main(i) == p) if kind == "assign" else (p in projects._members_of(i)) for i in found):
            continue
        path = " › ".join(projects.path_names(reg, p))
        if want and want not in page_model.fold(path) and not any(want in page_model.fold(a) for a in row["aliases"]):
            continue
        rows.append({"id": p, "name": row["name"], "path": path})
    rows.sort(key=lambda r: page_model.fold(r["path"]))
    return {"rows": rows[:PLACES_SHOWN], "more": max(0, len(rows) - PLACES_SHOWN)}


def homes(reg, item):
    """The live projects a thing is in, main first: [{"id", "name"}] (for "Not in ...")."""
    return [{"id": p, "name": projects.get(reg, p)["name"]} for p in projects._members_of(item)
            if projects.exists(reg, p) and not projects.hidden(reg, p)]


def why(reg, item):
    """Lines saying where a thing is kept and why you can trust it (T4): only what is stored."""
    main = projects._main(item)
    live = lambda p: projects.exists(reg, p) and not projects.hidden(reg, p)
    lines = []
    if main and live(main):
        lines.append(f"Main project: {' › '.join(projects.path_names(reg, main))}.")
    else:
        lines.append("Not in any project yet. Move it to one and it stays there.")
    also = [projects.get(reg, p)["name"] for p in item.get("also_in", []) if live(p)]
    if also:
        lines.append("Also in " + ", ".join(also) + ".")
    kept_out = [projects.get(reg, p)["name"] for p in item.get("not_in", []) if projects.exists(reg, p)]
    if kept_out:
        lines.append("Never suggested for " + ", ".join(kept_out) + ".")
    return lines


# ---------------------------------------------------------------- the pill files things by name

def file_by_name(reg, items, ids, name):
    """The pill's picker and suggestions say a project by name. Put the things in the project of that
    name (made at the top level when there is none yet), so the pill and the window agree (T6).
    Returns the ids that were found."""
    clean = projects.clean(name)
    if not clean:
        return []
    pid = projects.find(reg, clean, any_depth=True) or projects.create(reg, clean)
    return projects.move_to(reg, items, ids, pid)


def unfile_main(reg, items, ids):
    """"Take it out" on the pill: out of the main project (the next "also in" takes over). Returns the ids."""
    out = []
    for iid in ids:
        main = projects._main(items[iid]) if iid in items else None
        if main:
            projects.remove_from(reg, items, [iid], main)
            out.append(iid)
    return out


def decline_by_name(reg, items, ids, name):
    """"Not this project" on the pill: never suggest `name` for these again, as in the window (R14)."""
    pid = projects.find(reg, projects.clean(name), any_depth=True)
    if pid:
        for item in (items[i] for i in ids if i in items):
            if pid not in item.setdefault("not_in", []):
                item["not_in"].append(pid)
