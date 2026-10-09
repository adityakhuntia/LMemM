"""LMemM - projects: the places you file things in. Plain functions, no UI, all tested.

A project has a name and a parent, to any depth. A thing (an item) belongs to one *main*
project and may also be in others. The registry lives in its own small file
(data/memory/projects.json) so the menu, the window, the CLI and the tracker can each change
it without rewriting the whole memory file.

The rules (also listed in rules.py, R12-R15):

    R12  Projects nest to any depth and never loop. A project cannot go inside itself or
         inside anything it contains. Two projects in the same place never share a name.
    R13  A thing has at most one main project and any number of "also in" projects. Counts,
         pick up and "needs you" use the main project and roll up the tree, so a thing is
         never counted twice.
    R14  "Not this project" is permanent for automatic suggestions. Only you putting the thing
         there again lifts it.
    R15  Nothing is lost by accident. Archive hides a project and everything in it, and can be
         undone. Delete asks what happens to the things. Merge keeps the old name as an alias,
         so what you typed before still finds it.

Items keep two fields the older code reads: item["project"] (the main project's name) and,
new here, item["project_id"], item["also_in"] (ids) and item["not_in"] (ids).
"""

import json
import os
from datetime import datetime

import config
import notes

VERSION = 1


# ---------------------------------------------------------------- the registry

def empty():
    return {"version": VERSION, "next": 1, "projects": {}}


def clean(name):
    return " ".join((name or "").split())


def key(name):
    return clean(name).casefold()


def exists(reg, pid):
    return pid in reg["projects"]


def get(reg, pid):
    try:
        return reg["projects"][pid]
    except KeyError:
        raise ValueError("That project does not exist any more.") from None


def children(reg, pid=None):
    """The projects directly inside `pid` (None: top level), in the order they were made."""
    return [p["id"] for p in reg["projects"].values() if p["parent"] == pid]


def descendants(reg, pid):
    """Everything inside `pid`, any depth, not including `pid`."""
    out, todo = [], children(reg, pid)
    while todo:
        cur = todo.pop(0)
        out.append(cur)
        todo.extend(children(reg, cur))
    return out


def ancestors(reg, pid):
    """The parents of `pid`, nearest first."""
    out, cur = [], get(reg, pid)["parent"]
    while cur is not None:
        out.append(cur)
        cur = get(reg, cur)["parent"]
    return out


def path(reg, pid):
    """From the top: [grandparent, parent, pid]."""
    return list(reversed(ancestors(reg, pid))) + [pid]


def path_names(reg, pid):
    return [get(reg, i)["name"] for i in path(reg, pid)]


def depth(reg, pid):
    return len(ancestors(reg, pid))


def hidden(reg, pid):
    """Archived, or inside something archived (R15)."""
    return any(get(reg, i)["archived"] for i in [pid] + ancestors(reg, pid))


def _sibling_named(reg, parent, name, except_id=None):
    for pid in children(reg, parent):
        if pid != except_id and key(get(reg, pid)["name"]) == key(name):
            return pid
    return None


def find(reg, name, parent=None, any_depth=False):
    """A project by name (or by an alias it picked up in a merge). Case and spacing do not
    matter. By default only inside `parent`; any_depth looks everywhere."""
    wanted = key(name)
    if not wanted:
        return None
    for p in reg["projects"].values():
        if not any_depth and p["parent"] != parent:
            continue
        if key(p["name"]) == wanted or wanted in {key(a) for a in p["aliases"]}:
            return p["id"]
    return None


def create(reg, name, parent=None, now=None):
    """Make a project. Returns its id. ValueError says, in words, why not."""
    name = clean(name)
    if not name:
        raise ValueError("Give the project a name.")
    if parent is not None:
        get(reg, parent)
    if _sibling_named(reg, parent, name):
        raise ValueError(f"There is already a project called “{name}” here.")
    pid = f"p{reg['next']}"
    reg["next"] += 1
    reg["projects"][pid] = {"id": pid, "name": name, "parent": parent, "archived": False, "aliases": [],
                            "created": (now or datetime.now()).isoformat(timespec="seconds")}
    return pid


def rename(reg, pid, name, items=None):
    """Rename. Pass `items` so the name older code reads (item["project"]) follows."""
    name = clean(name)
    if not name:
        raise ValueError("Give the project a name.")
    p = get(reg, pid)
    if _sibling_named(reg, p["parent"], name, except_id=pid):
        raise ValueError(f"There is already a project called “{name}” here.")
    p["name"] = name
    for item in (items or {}).values():
        if _main(item) == pid:
            _name_it(reg, item)


def move(reg, pid, parent=None):
    """Put `pid` (with everything in it) inside `parent`, or at the top (R12)."""
    p = get(reg, pid)
    if parent is not None:
        get(reg, parent)
        if parent == pid or parent in descendants(reg, pid):
            raise ValueError("A project cannot go inside itself.")
    if _sibling_named(reg, parent, p["name"], except_id=pid):
        raise ValueError(f"There is already a project called “{p['name']}” there.")
    p["parent"] = parent


def archive(reg, pid):
    get(reg, pid)["archived"] = True


def restore(reg, pid):
    """Bring a project back. Anything above it that is archived comes back too, or it would
    still be out of sight."""
    for i in [pid] + ancestors(reg, pid):
        get(reg, i)["archived"] = False


# ---------------------------------------------------------------- things in projects

def _main(item):
    return item.get("project_id")


def _members_of(item):
    """The projects a thing is in, main first."""
    mine = [_main(item)] if _main(item) else []
    return mine + [p for p in item.get("also_in", []) if p not in mine]


def _name_it(reg, item):
    """Keep item["project"] (the name older code reads) in step with the main project."""
    pid = _main(item)
    if pid and exists(reg, pid):
        item["project"] = get(reg, pid)["name"]
    else:
        item.pop("project", None)
        item.pop("project_id", None)


def _each(items, ids):
    return [items[i] for i in ids if i in items]


def _tidy(item):
    for field in ("also_in", "not_in"):
        if field in item and not item[field]:
            del item[field]


def move_to(reg, items, ids, pid):
    """The thing's main project is now `pid`. Where it was before no longer holds it."""
    get(reg, pid)
    found = _each(items, ids)
    for item in found:
        item["project_id"] = pid
        item["also_in"] = [p for p in item.get("also_in", []) if p != pid]
        item["not_in"] = [p for p in item.get("not_in", []) if p != pid]       # you chose it (R14)
        _tidy(item)
        _name_it(reg, item)
    return [i["id"] for i in found]


def add_also(reg, items, ids, pid):
    """Also in `pid`. A thing with no main project gets it as its main."""
    get(reg, pid)
    found = _each(items, ids)
    for item in found:
        item["not_in"] = [p for p in item.get("not_in", []) if p != pid]
        if not _main(item):
            item["project_id"] = pid
        elif _main(item) != pid and pid not in item.get("also_in", []):
            item.setdefault("also_in", []).append(pid)
        _tidy(item)
        _name_it(reg, item)
    return [i["id"] for i in found]


def make_main(reg, items, ids, pid):
    """Promote `pid` to main. The old main project keeps the thing as an "also in"."""
    get(reg, pid)
    found = _each(items, ids)
    for item in found:
        old = _main(item)
        item["project_id"] = pid
        also = [p for p in item.get("also_in", []) if p != pid]
        if old and old != pid and old not in also:
            also.insert(0, old)
        item["also_in"] = also
        item["not_in"] = [p for p in item.get("not_in", []) if p != pid]
        _tidy(item)
        _name_it(reg, item)
    return [i["id"] for i in found]


def remove_from(reg, items, ids, pid):
    """Take things out of `pid`. If it was their main project, the first "also in" takes over."""
    found = _each(items, ids)
    for item in found:
        also = [p for p in item.get("also_in", []) if p != pid]
        if _main(item) == pid:
            item.pop("project_id", None)
            if also:
                item["project_id"] = also.pop(0)
        item["also_in"] = also
        _tidy(item)
        _name_it(reg, item)
    return [i["id"] for i in found]


def not_this(reg, items, ids, pid):
    """"Not this project": out of it, and never suggested back into it (R14)."""
    remove_from(reg, items, ids, pid)
    found = _each(items, ids)
    for item in found:
        if pid not in item.setdefault("not_in", []):
            item["not_in"].append(pid)
    return [i["id"] for i in found]


def allowed(item, pid):
    """May an automatic suggestion put this thing in `pid`? (R14)"""
    return pid not in item.get("not_in", [])


def members(reg, items, pid, deep=True):
    """The things in `pid` (and, when deep, everything inside it), most recent first. A thing
    in two of those projects appears once."""
    wanted = {pid} | (set(descendants(reg, pid)) if deep else set())
    mine = [i for i in items.values() if wanted & set(_members_of(i))]
    return sorted(mine, key=lambda i: i.get("last_seen", ""), reverse=True)


def unassigned(items):
    """Things with no main project (the ones LMemM has not placed, or that lost theirs)."""
    return sorted((i for i in items.values() if not _main(i)), key=lambda i: i.get("last_seen", ""), reverse=True)


def counts(reg, items):
    """{project id: {"things", "open", "last"}} for every project, rolled up the tree by main
    project (R13). "open" is open notes; "last" is the latest last_seen, or None."""
    own = {pid: {"things": 0, "open": 0, "last": None} for pid in reg["projects"]}
    for item in items.values():
        pid = _main(item)
        if pid in own:
            row = own[pid]
            row["things"] += 1
            row["open"] += len(notes.open_notes(item))
            seen = item.get("last_seen")
            if seen and (row["last"] is None or seen > row["last"]):
                row["last"] = seen
    total = {pid: dict(row) for pid, row in own.items()}
    for pid in reg["projects"]:
        for up in ancestors(reg, pid):
            t, row = total[up], own[pid]
            t["things"] += row["things"]
            t["open"] += row["open"]
            if row["last"] and (t["last"] is None or row["last"] > t["last"]):
                t["last"] = row["last"]
    return total


# ---------------------------------------------------------------- merge and delete

def merge_plan(reg, items, src, target):
    """What a merge would do, for the preview: how many things and sub-projects move. ValueError
    when it cannot be done."""
    get(reg, src)
    get(reg, target)
    if src == target or target in descendants(reg, src):
        raise ValueError("A project cannot be merged into itself or into something inside it.")
    inside = {src} | set(descendants(reg, src))
    return {"things": sum(1 for i in items.values() if inside & set(_members_of(i))),
            "projects": len(inside) - 1, "from": get(reg, src)["name"], "into": get(reg, target)["name"]}


def merge(reg, items, src, target):
    """Everything in `src` goes into `target`; `src` disappears and its name becomes an alias of
    `target`. Sub-projects with the same name as one already in `target` merge into it (R15).
    Returns merge_plan()'s answer."""
    plan = merge_plan(reg, items, src, target)
    _merge(reg, items, src, target)
    return plan


def _merge(reg, items, src, target):
    s, t = get(reg, src), get(reg, target)
    for kid in children(reg, src):
        twin = _sibling_named(reg, target, get(reg, kid)["name"])
        if twin:
            _merge(reg, items, kid, twin)
        else:
            get(reg, kid)["parent"] = target
    for item in items.values():
        if src not in _members_of(item) and src not in item.get("not_in", []):
            continue
        main = _main(item) == src
        also = [target if p == src else p for p in item.get("also_in", [])]
        if main:
            item["project_id"] = target
        if _main(item) != src:
            also = [p for p in also if p != _main(item)]
        item["also_in"] = list(dict.fromkeys(also))
        if src in item.get("not_in", []):
            item["not_in"] = list(dict.fromkeys(target if p == src else p for p in item["not_in"]))
        _tidy(item)
        _name_it(reg, item)
    for alias in [s["name"]] + s["aliases"]:
        if key(alias) != key(t["name"]) and key(alias) not in {key(a) for a in t["aliases"]}:
            t["aliases"].append(alias)
    del reg["projects"][src]


def delete(reg, items, pid, forget=False):
    """Delete a project and everything inside it. Things whose main project goes move to their
    first remaining "also in", or end up with no project. With forget=True the ids of things
    that ended up with no project at all are returned in "forget" for the caller to remove from
    memory; otherwise they stay, unplaced. Returns {"projects": n, "things": n, "forget": [ids]}."""
    gone = {pid} | set(descendants(reg, pid))
    get(reg, pid)
    touched, orphaned = 0, []
    for item in items.values():
        mine = set(_members_of(item))
        if not mine & gone:
            continue
        touched += 1
        for p in sorted(mine & gone):
            remove_from(reg, {item["id"]: item}, [item["id"]], p)
        if not _main(item):
            orphaned.append(item["id"])
        item["not_in"] = [p for p in item.get("not_in", []) if p not in gone]
        _tidy(item)
    for p in gone:
        del reg["projects"][p]
    return {"projects": len(gone), "things": touched, "forget": orphaned if forget else []}


# ---------------------------------------------------------------- coming from names

def adopt(reg, items):
    """Older versions filed things by name (item["project"]). Give each name a top-level project
    and point the item at it; clear ids that no longer exist. Safe to run again. Returns how
    many items changed."""
    changed = 0
    for item in items.values():
        pid = _main(item)
        if pid and not exists(reg, pid):
            item.pop("project_id", None)
            changed += 1
            pid = None
        item["also_in"] = [p for p in item.get("also_in", []) if exists(reg, p)]
        item["not_in"] = [p for p in item.get("not_in", []) if exists(reg, p)]
        _tidy(item)
        name = clean(item.get("project"))
        if pid or not name:
            continue
        found = find(reg, name, any_depth=True)
        if found is None:
            found = create(reg, name)
        item["project_id"] = found
        _name_it(reg, item)
        changed += 1
    return changed


# ---------------------------------------------------------------- finding and showing

def resolve(reg, text):
    """A project from what you typed: "Pricing/Q3 launch" from the top, or just "India" when only
    one project has that name (or one at the top level: a bare name means that one first). Case, spacing and merge aliases do not matter. ValueError says
    what was wrong, in words."""
    parts = [clean(x) for x in (text or "").replace("›", "/").split("/") if clean(x)]
    if not parts:
        raise ValueError("Say which project.")
    if len(parts) == 1:
        hits = [p["id"] for p in reg["projects"].values()
                if key(p["name"]) == key(parts[0]) or key(parts[0]) in {key(a) for a in p["aliases"]}]
        top = [h for h in hits if reg["projects"][h]["parent"] is None]
        if len(top) == 1:                                  # a bare name means the top-level one first
            return top[0]
        if len(hits) > 1:
            where = ", ".join("/".join(path_names(reg, h)) for h in hits)
            raise ValueError(f"More than one project is called “{parts[0]}”: {where}. Use the full path.")
        if hits:
            return hits[0]
    else:
        cur = None
        for part in parts:
            cur = find(reg, part, parent=cur)
            if cur is None:
                break
        if cur is not None:
            return cur
    raise ValueError(f"There is no project called “{'/'.join(parts)}”.")


def tree_lines(reg, items, include_hidden=False):
    """The tree as text, one line per project: name, things, open notes (rolled up, R13)."""
    total = counts(reg, items)
    out = []

    def walk(parent, level):
        for pid in children(reg, parent):
            p = get(reg, pid)
            if p["archived"] and not include_hidden:
                continue
            row = total[pid]
            bits = [f"{row['things']} thing{'s' * (row['things'] != 1)}"]
            if row["open"]:
                bits.append(f"{row['open']} open")
            if p["archived"]:
                bits.append("archived")
            out.append("  " * level + p["name"] + "  · " + " · ".join(bits))
            walk(pid, level + 1)
    walk(None, 0)
    return out


# ---------------------------------------------------------------- the file

def load():
    """The registry on disk, or a new empty one. A file that cannot be read is never replaced
    by an empty one: ValueError says so (the same promise as store.save_user)."""
    file = config.paths().projects_file
    if not os.path.exists(file):
        return empty()
    try:
        with open(file) as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as error:
        raise ValueError(f"Cannot read {file}: {error}") from error
    if not isinstance(doc, dict) or not isinstance(doc.get("projects"), dict):
        raise ValueError(f"Cannot read {file}: not a project list")
    doc.setdefault("version", VERSION)
    doc.setdefault("next", 1 + max([int(k[1:]) for k in doc["projects"] if k[1:].isdigit()] or [0]))
    return doc


def save(reg):
    import store
    store.write_json(config.paths().projects_file, reg)
