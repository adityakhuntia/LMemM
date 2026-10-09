"""LMemM - changing projects from the window, as plain functions. No UI, all tested.

The window offers a handful of actions on the project tree: make, rename, move, archive,
bring back, merge, delete. Each is one function in projects.py; this file adds what the window
needs around them: the words that confirm each one, which targets make sense, a preview before
the two that move many things, and Undo.

    A1  Undo beats "are you sure". Every action can be undone: before it runs the window takes a
        snapshot of the project tree and of each thing's project fields, and Undo puts both back
        (a thing you filed somewhere else since is left where you put it).
    A2  Nothing here deletes a remembered thing. Deleting a project leaves its things where they
        are, with no project (projects.delete with forget=False). Forgetting things is a
        different, separate promise that is not offered here.
    A3  Merge and Delete show what they will do first (how many things and sub-projects), and
        only they ask. The rest happen at once and say so with Undo.
    A4  Targets are only places that make sense: never the project itself or anything inside it,
        never an archived place, never where it already is. A move can also go to the top level.
    A5  Every error is a sentence a person can act on (the ones projects.py raises), never a
        traceback; the window shows it and keeps the dialog open.
    A6  After an action the window shows the project that makes sense: the new one, the one that
        was changed, the one merged into, or the parent of what went away.
"""

import copy

import page_model
import projects
import thing_actions

FIELDS = ("project", "project_id", "also_in", "not_in")           # what a project change can touch on a thing
ACTIONS = ("new", "rename", "move", "archive", "restore", "merge", "delete") + thing_actions.ACTIONS


# ---------------------------------------------------------------- undo (A1)

def _fields(items):
    return {i: {k: copy.deepcopy(v) for k, v in item.items() if k in FIELDS} for i, item in items.items()
            if any(k in item for k in FIELDS)}


def snapshot(reg, items):
    """The project tree and every thing's project fields, copied."""
    return {"reg": copy.deepcopy(reg), "fields": _fields(items)}


def do(reg, items, action, **args):
    """run(), plus what Undo needs: the state before, and the things' fields right after, so Undo
    only puts back what this action changed and leaves anything filed since."""
    before = snapshot(reg, items)
    gone = ({i: copy.deepcopy(items[i]) for i in args.get("ids", ()) if i in items}   # Forget removes things: keep them for Undo
            if action == "forget" else {})
    result = run(reg, items, action, **args)
    gone = {i: item for i, item in gone.items() if i not in items}
    return {**result, "undo": {"before": before, "after": _fields(items), "gone": gone}}


def undo(reg, items, undo):
    """Put the tree back and each thing's project fields, in place. A thing whose fields changed
    again since the action (you filed it somewhere) is left as you left it."""
    reg.clear()
    reg.update(copy.deepcopy(undo["before"]["reg"]))
    for iid, item in undo.get("gone", {}).items():                           # forgotten things come back whole
        items.setdefault(iid, copy.deepcopy(item))
    for iid, item in items.items():
        now = {k: item[k] for k in FIELDS if k in item}
        if now != undo["after"].get(iid, {}):
            continue
        before = undo["before"]["fields"].get(iid, {})
        for k in FIELDS:
            if k in before:
                item[k] = copy.deepcopy(before[k])
            else:
                item.pop(k, None)


# ---------------------------------------------------------------- doing things (A2, A6)

def _name(reg, pid):
    return projects.get(reg, pid)["name"]


def run(reg, items, action, pid=None, name=None, parent=None, target=None, ids=(), here=None):
    """Do one action. Returns {"message", "go"}: the sentence for the toast and the project to
    show next (None: all projects). ValueError says why not, in words (A5). Actions on things
    (thing_actions.py) also say "stay": the page does not change."""
    if action in thing_actions.ACTIONS:
        return thing_actions.run(reg, items, action, ids, pid, here)
    if action == "new":
        new = projects.create(reg, name, parent)
        return {"message": f"Made “{_name(reg, new)}”" + (f" in “{_name(reg, parent)}”" if parent else ""), "go": new}
    if action == "rename":
        old = _name(reg, pid)
        projects.rename(reg, pid, name, items)
        return {"message": f"Renamed “{old}” to “{_name(reg, pid)}”", "go": pid}
    if action == "move":
        projects.move(reg, pid, parent)
        where = f"into “{_name(reg, parent)}”" if parent else "to the top"
        return {"message": f"Moved “{_name(reg, pid)}” {where}", "go": pid}
    if action == "archive":
        up = projects.get(reg, pid)["parent"]
        projects.archive(reg, pid)
        return {"message": f"Archived “{_name(reg, pid)}”", "go": up}
    if action == "restore":
        projects.restore(reg, pid)
        return {"message": f"Brought back “{_name(reg, pid)}”", "go": pid}
    if action == "merge":
        plan = projects.merge(reg, items, pid, target)
        return {"message": f"Merged “{plan['from']}” into “{plan['into']}” · {plan['things']:,} "
                           f"thing{'s' * (plan['things'] != 1)}", "go": target}
    if action == "delete":
        old, up = _name(reg, pid), projects.get(reg, pid)["parent"]
        result = projects.delete(reg, items, pid, forget=False)
        return {"message": f"Deleted “{old}” · {result['things']:,} thing{'s' * (result['things'] != 1)} kept", "go": up}
    raise ValueError("That is not something projects can do.")


# ---------------------------------------------------------------- the question before merge and delete (A3)

def plan(reg, items, action, pid, target=None):
    """{"title", "text", "button"} for the dialog before Merge or Delete."""
    if action == "merge":
        p = projects.merge_plan(reg, items, pid, target)
        subs = f" and {p['projects']:,} sub-project{'s' * (p['projects'] != 1)}" if p["projects"] else ""
        return {"title": f"Merge “{p['from']}” into “{p['into']}”?",
                "text": f"{p['things']:,} thing{'s' * (p['things'] != 1)}{subs} move into “{p['into']}”. "
                        f"“{p['from']}” goes away, and its name still finds “{p['into']}”. You can undo this.",
                "button": "Merge"}
    if action == "delete":
        projects.get(reg, pid)
        gone = {pid} | set(projects.descendants(reg, pid))
        things = sum(1 for i in items.values() if gone & set(projects._members_of(i)))
        subs = len(gone) - 1
        extra = f" and its {subs:,} sub-project{'s' * (subs != 1)}" if subs else ""
        return {"title": f"Delete “{_name(reg, pid)}”{extra}?",
                "text": f"Your {things:,} thing{'s' * (things != 1)} in {'them' if subs else 'it'} stay in LMemM, "
                        "without a project. Nothing you wrote is lost. You can undo this.",
                "button": "Delete"}
    raise ValueError("That does not need a question first.")


# ---------------------------------------------------------------- where it can go (A4)

TARGETS_SHOWN = 40


def targets(reg, pid, kind, query=""):
    """Places `pid` can be moved to ("move") or merged into ("merge"), for the picker: a list of
    {"id", "name", "path"} and how many more match. A move also offers the top level."""
    cannot = {pid} | set(projects.descendants(reg, pid))
    here = projects.get(reg, pid)["parent"]
    want = page_model.fold(query)
    rows = []
    for p, row in reg["projects"].items():
        if p in cannot or projects.hidden(reg, p) or (kind == "move" and p == here):
            continue
        path = " › ".join(projects.path_names(reg, p))
        if want and want not in page_model.fold(path) and not any(want in page_model.fold(a) for a in row["aliases"]):
            continue
        rows.append({"id": p, "name": row["name"], "path": path})
    rows.sort(key=lambda r: page_model.fold(r["path"]))
    top = [{"id": None, "name": "Top level", "path": "Not inside any project"}] if kind == "move" and here is not None and not want else []
    return {"rows": top + rows[:TARGETS_SHOWN], "more": max(0, len(rows) - TARGETS_SHOWN)}
