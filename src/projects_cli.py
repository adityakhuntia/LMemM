"""LMemM - `lmemm.py projects`: look at and shape the project tree from the terminal. No Mac
needed; the menu bar and the project window use the same projects.py calls.

    lmemm.py projects [--all]                       the tree, with things and open notes
    lmemm.py projects new NAME [--in PATH]
    lmemm.py projects rename PATH NEW_NAME
    lmemm.py projects move PATH [--to PATH]         (no --to: to the top)
    lmemm.py projects archive PATH | restore PATH
    lmemm.py projects merge PATH --into PATH [--dry-run]
    lmemm.py projects delete PATH [--forget] (--dry-run | --confirm)

PATH is "Pricing/Q3 launch", or just "India" when only one project has that name.
Anything that changes which things are in a project needs LMemM stopped, so the running
tracker does not write over it.
"""

import argparse

import projects
import store


def _parser():
    p = argparse.ArgumentParser(prog="lmemm.py projects", add_help=False)
    p.add_argument("words", nargs="*")
    p.add_argument("--all", action="store_true")
    p.add_argument("--in", dest="inside")
    p.add_argument("--to", dest="to")
    p.add_argument("--into", dest="into")
    p.add_argument("--forget", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm", action="store_true")
    return p


def run(args, running=False, save_items=None, out=print):
    """Do one command. `running`: the tracker is running. `save_items(items)` writes memory.
    Raises ValueError with a sentence for the person; the caller prints it and stops."""
    opts = _parser().parse_args(args)
    words = opts.words
    cmd = words[0] if words else "tree"
    if cmd not in {"tree", "new", "rename", "move", "archive", "restore", "merge", "delete"}:
        raise ValueError(f"I do not know “{cmd}”. Try: new, rename, move, archive, restore, merge, delete.")
    reg, items = projects.load(), store.load_items()
    touches = cmd in {"rename", "merge", "delete"}
    if touches and running:
        raise ValueError("LMemM is running. Stop it first (./run.sh stop), so nothing is written over this.")
    adopted = projects.adopt(reg, items)

    def finish(items_changed=False):
        projects.save(reg)
        if items_changed and not running and save_items:
            save_items(items)

    if cmd == "tree":
        lines = projects.tree_lines(reg, items, include_hidden=opts.all)
        out("\n".join(lines) if lines else "No projects yet. Make one: lmemm.py projects new \"Pricing\"")
        left = len(projects.unassigned(items))
        if left:
            out(f"\n{left} thing{'s' * (left != 1)} not in a project")
        finish(items_changed=bool(adopted))
        return
    if cmd == "new":
        if len(words) != 2:
            raise ValueError("Usage: lmemm.py projects new NAME [--in PATH]")
        parent = projects.resolve(reg, opts.inside) if opts.inside else None
        pid = projects.create(reg, words[1], parent)
        finish(items_changed=bool(adopted))
        out("Made " + "/".join(projects.path_names(reg, pid)))
    elif cmd == "rename":
        if len(words) != 3:
            raise ValueError("Usage: lmemm.py projects rename PATH NEW_NAME")
        pid = projects.resolve(reg, words[1])
        projects.rename(reg, pid, words[2], items)
        finish(items_changed=True)
        out("Renamed to " + "/".join(projects.path_names(reg, pid)))
    elif cmd == "move":
        if len(words) != 2:
            raise ValueError("Usage: lmemm.py projects move PATH [--to PATH]")
        pid = projects.resolve(reg, words[1])
        projects.move(reg, pid, projects.resolve(reg, opts.to) if opts.to else None)
        finish(items_changed=bool(adopted))
        out("Now at " + "/".join(projects.path_names(reg, pid)))
    elif cmd in {"archive", "restore"}:
        if len(words) != 2:
            raise ValueError(f"Usage: lmemm.py projects {cmd} PATH")
        pid = projects.resolve(reg, words[1])
        (projects.archive if cmd == "archive" else projects.restore)(reg, pid)
        finish(items_changed=bool(adopted))
        out(("Archived " if cmd == "archive" else "Restored ") + "/".join(projects.path_names(reg, pid)))
    elif cmd == "merge":
        if len(words) != 2 or not opts.into:
            raise ValueError("Usage: lmemm.py projects merge PATH --into PATH [--dry-run]")
        src, target = projects.resolve(reg, words[1]), projects.resolve(reg, opts.into)
        plan = projects.merge_plan(reg, items, src, target)
        line = (f"{plan['things']} things and {plan['projects']} sub-projects move from “{plan['from']}” "
                f"into “{plan['into']}”. “{plan['from']}” stays findable as a name.")
        if opts.dry_run:
            out(line + "\nNothing was changed.")
            return
        projects.merge(reg, items, src, target)
        finish(items_changed=True)
        out("Merged. " + line)
    elif cmd == "delete":
        if len(words) != 2 or not (opts.dry_run or opts.confirm):
            raise ValueError("Usage: lmemm.py projects delete PATH [--forget] (--dry-run | --confirm)")
        pid = projects.resolve(reg, words[1])
        inside = [pid] + projects.descendants(reg, pid)
        things = projects.members(reg, items, pid)
        line = (f"“{projects.get(reg, pid)['name']}” has {len(inside) - 1} sub-projects and {len(things)} things. "
                + ("Things left in no project are forgotten." if opts.forget else "The things stay, in no project."))
        if opts.dry_run:
            out(line + "\nNothing was changed. Run with --confirm to delete.")
            return
        result = projects.delete(reg, items, pid, forget=opts.forget)
        for iid in result["forget"]:
            items.pop(iid, None)
        finish(items_changed=True)
        out(f"Deleted {result['projects']} project(s). " + (f"Forgot {len(result['forget'])} thing(s)." if opts.forget else ""))
