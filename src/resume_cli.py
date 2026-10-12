"""LMemM - `lmemm.py catchup`: the Resume brief as text, from live memory, a snapshot file, or the demo. No UI.

    catchup PROJECT                 a filed project (name as in the project tree)
    catchup --scope "PR 25"         things not filed anywhere, grouped into work threads, led by the one naming the scope
    catchup --scope "PR 25" --pick ID   resume one of the candidates it listed
    --memory FILE   read this memory.json instead (read only; nothing is written)   --trail FILE   the run's trail .jsonl (what you typed)   --now ISO   the moment to resume at
    --demo          the made-up projects      --copy   put the text on the clipboard (macOS)
    --feedback FILE your corrections (resume_feedback.py); default: the live file. Never memory.
    --mark right|outdated   --replace "words"   --exclude ITEM   correct what was just shown, then show it again
"""

import json
import sys
from datetime import datetime

import page_model
import projects
import resume
import resume_demo
import resume_feedback
import store
import tasks


def _flag(args, name):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def run(args, copy=None):
    now = datetime.fromisoformat(_flag(args, "--now")) if _flag(args, "--now") else datetime.now()
    scope, pick, memory = _flag(args, "--scope"), _flag(args, "--pick"), _flag(args, "--memory")
    trail, fb_file = _flag(args, "--trail"), _flag(args, "--feedback")
    mark, replace, exclude = _flag(args, "--mark"), _flag(args, "--replace"), _flag(args, "--exclude")
    skip = {v for v in (scope, pick, memory, trail, fb_file, mark, replace, exclude, _flag(args, "--now")) if v}
    if not fb_file and not memory and "--demo" not in args:
        import config
        fb_file = config.paths().resume_feedback_file                # live use; a snapshot or demo run never touches it
    fb = resume_feedback.load(fb_file) if fb_file else resume_feedback.empty()
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
    def make():
        if scope or not words:
            return resume.brief_scope(items, scope, now, book, pick, events, fb)
        names = {p["name"].casefold(): q for q, p in reg["projects"].items() if not p["archived"]}
        pid = names.get(" ".join(words).casefold())
        if not pid:
            sys.exit("No project called that. Try one of: " + (", ".join(p["name"] for p in reg["projects"].values()) or "none yet")
                     + '  (or --scope "PR 25" for things not filed in a project)')
        return resume.brief(reg, items, pid, now, book, events, fb)
    b = make()
    if (mark or replace or exclude) and fb_file:                      # your word on it, kept in its own file
        step = (b.get("next") or {})
        stamp = now.isoformat(timespec="seconds")
        if exclude:
            resume_feedback.record(fb, "exclude", item_id=exclude, at=stamp)
        elif step.get("key"):
            resume_feedback.record(fb, "replace" if replace else mark, step_key=step["key"], text=replace, at=stamp)
        resume_feedback.save(fb_file, fb)
        b = make()
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
