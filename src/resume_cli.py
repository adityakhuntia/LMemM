"""LMemM - `lmemm.py catchup`: the Resume brief as text, from live memory, a snapshot file, or the demo. No UI.

    catchup PROJECT                 a filed project (name as in the project tree)
    catchup --scope "PR 25"         things not filed anywhere, grouped into work threads, led by the one naming the scope
    catchup --scope "PR 25" --pick ID   resume one of the candidates it listed
    --memory FILE   read this memory.json instead (read only; nothing is written)   --trail FILE   the run's trail .jsonl (what you typed)   --now ISO   the moment to resume at
    --demo          the made-up projects      --copy   put the text on the clipboard (macOS)
"""

import json
import sys
from datetime import datetime

import page_model
import projects
import resume
import resume_demo
import store
import tasks


def _flag(args, name):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def run(args, copy=None):
    now = datetime.fromisoformat(_flag(args, "--now")) if _flag(args, "--now") else datetime.now()
    scope, pick, memory = _flag(args, "--scope"), _flag(args, "--pick"), _flag(args, "--memory")
    trail = _flag(args, "--trail")
    skip = {v for v in (scope, pick, memory, trail, _flag(args, "--now")) if v}
    events = None
    if trail:
        with open(trail) as fh:                                       # read only
            events = [json.loads(line) for line in fh if line.strip()]
    words = [a for a in args if not a.startswith("--") and a not in skip]
    if "--demo" in args:
        reg, items, book = resume_demo.build(now)
    elif memory:
        with open(memory) as fh:                                   # read only
            items = {i["id"]: i for i in json.load(fh)["items"]}
        reg, book = projects.empty(), {}
    else:
        try:
            items, reg, book = store.load_items(), projects.load(), tasks.load_tasks()
        except ValueError as error:
            sys.exit(str(error))
    if scope or not words:
        b = resume.brief_scope(items, scope, now, book, pick, events)
    else:
        names = {p["name"].casefold(): pid for pid, p in reg["projects"].items() if not p["archived"]}
        pid = names.get(" ".join(words).casefold())
        if not pid:
            sys.exit("No project called that. Try one of: " + (", ".join(p["name"] for p in reg["projects"].values()) or "none yet")
                     + '  (or --scope "PR 25" for things not filed in a project)')
        b = resume.brief(reg, items, pid, now, book)
    text = render(b)
    print(text)
    if "--copy" in args and copy:
        copy(resume.as_text(b))
    return b


def render(b):
    if b["state"] == "ambiguous":
        lines = [b["note"], ""]
        for n, c in enumerate(b["candidates"], 1):
            lines.append(f"  {n}. {c['title']}  ({page_model.plural(c['things'], 'thing')}, {page_model.plural(c['notes'], 'open note')}, {resume.said(c['ago'])})   --pick {c['id']}")
        return "\n".join(lines)
    if b["state"] == "empty":
        return b["note"]
    return resume.as_text(b)
