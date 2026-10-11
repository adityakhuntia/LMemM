"""LMemM - the safe next step: what the pill offers while you work. Suggest-only, as plain functions. No UI.

`tasks.py` works out what you are trying to get done. This file keeps what follows from it, so the pill can show it:

    next   "Check the trigger runs on a weekday"      the open step of a task
    link   "The reminder text in ChatGPT is what you
            are pasting into the Apps Script"          two things that belong together, even in different apps

    N1  Suggest only. Nothing here clicks, types, files or sends. It is a sentence you may act on yourself.
    N2  Say it once. The same sentence never comes back after you dismissed it or marked it done (N3 keeps the
        memory of that for the day), and a repeated run only refreshes the entry already waiting.
    N3  Few and fresh. At most MAX_OPEN wait; the oldest go first; anything older than KEEP_HOURS, or about a
        thing that is gone, is dropped on every read.
    N4  Links need both ends: two different things that still exist, and a reason taken from the text.
    N5  No addresses, no secrets: a sentence is cleaned before it is kept (tasks.clean).
"""

import json
import os
import re
from datetime import datetime, timedelta

import config
import store
import tasks

KEEP_HOURS = 12
MAX_OPEN = 5
TEXT_CHARS = 140
STATES = ("new", "done", "dismissed")


def empty():
    return {"version": 1, "n": 0, "steps": []}


def path():
    return os.path.join(config.paths().memory_dir, "nextsteps.json")


def load():
    try:
        with open(path()) as fh:
            doc = json.load(fh)
        if isinstance(doc.get("steps"), list):
            return {**empty(), **doc}
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return empty()


def save(doc):
    store.write_json(path(), doc)


def _key(kind, text):
    return kind + ":" + re.sub(r"[^a-z0-9]", "", text.lower())[:80]


def _iso(now):
    return now.isoformat(timespec="seconds")


def _add(doc, kind, text, ids, task, now):
    text = tasks.clean(text, TEXT_CHARS)
    if not text or not ids:
        return None
    key = _key(kind, text)
    for step in doc["steps"]:
        if step["key"] == key:
            if step["state"] == "new":
                step.update(items=ids, task=task, seen=_iso(now))      # N2: refresh, never duplicate
            return None
    doc["n"] += 1
    step = {"id": f"n{doc['n']}", "key": key, "kind": kind, "text": text, "items": ids, "task": task,
            "state": "new", "made": _iso(now), "seen": _iso(now)}
    doc["steps"].append(step)
    return step


def ingest(doc, result, items, now=None):
    """Fold one `tasks.run` result in. Returns the steps that are new."""
    now = now or datetime.now()
    added = []
    for t in result.get("tasks") or []:
        ids = [i for i in t.get("items", []) if i in items]
        if t.get("open"):
            added.append(_add(doc, "next", t["open"], ids, t.get("title"), now))
    for link in result.get("links") or []:
        ids = [i for i in dict.fromkeys(link.get("items", [])) if i in items]
        if len(ids) == 2 and link.get("why"):                                     # N4
            added.append(_add(doc, "link", link["why"], ids, None, now))
    tidy(doc, items, now)
    return [s for s in added if s and s in doc["steps"]]


def tidy(doc, items, now=None):
    """N3: drop what is stale, gone or surplus. Returns True when anything changed."""
    now = now or datetime.now()
    before = repr(doc)
    floor = now - timedelta(hours=KEEP_HOURS)
    keep = []
    for step in doc["steps"]:
        try:
            fresh = datetime.fromisoformat(step["seen"]) >= floor
        except (KeyError, ValueError):
            fresh = False
        if step["state"] == "new":
            step["items"] = [i for i in step["items"] if i in items]
            if not fresh or (step["kind"] == "link" and len(step["items"]) < 2) or not step["items"]:
                continue
        elif not fresh:
            continue                                                               # the day's memory of an answer ends
        keep.append(step)
    waiting = [s for s in keep if s["state"] == "new"]
    for old in sorted(waiting, key=lambda s: s["seen"])[:-MAX_OPEN] if len(waiting) > MAX_OPEN else []:
        keep.remove(old)
    doc["steps"] = keep
    return repr(doc) != before


def view(doc, items, now=None):
    """What the pill draws: {"count", "steps": [{id, kind, text, task, things: [{app, title}], age}]}, newest first."""
    now = now or datetime.now()
    tidy(doc, items, now)
    rows = []
    for step in sorted((s for s in doc["steps"] if s["state"] == "new"), key=lambda s: s["seen"], reverse=True):
        try:
            minutes = int((now - datetime.fromisoformat(step["seen"])).total_seconds() // 60)
        except ValueError:
            minutes = 0
        rows.append({"id": step["id"], "kind": step["kind"], "text": step["text"], "task": step.get("task"),
                     "things": [{"app": items[i].get("app"), "title": items[i].get("title") or items[i].get("doing")}
                                for i in step["items"]],
                     "age": "just now" if minutes < 2 else f"{minutes} min ago" if minutes < 90 else f"{minutes // 60} h ago"})
    return {"count": len(rows), "steps": rows}


def answer(doc, sid, state):
    """Mark a step done or dismissed. ValueError when it is gone (nothing changes)."""
    if state not in STATES[1:]:
        raise ValueError("A step can be done or dismissed.")
    for step in doc["steps"]:
        if step["id"] == sid and step["state"] == "new":
            step["state"] = state
            step["seen"] = _iso(datetime.now())
            return step
    raise ValueError("That suggestion is gone already. Nothing was changed.")
