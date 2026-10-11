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

What it offers (the pipeline, in the order the pill shows it). Only `next` and `link` come from the model (they
arrive with a `tasks` run); the other two are worked out here from what is stored, so they cost no tokens:

    resume   "Back to “Verify the follow-up automation”"   you return to a task after hours away: what you were
                                                              making, the last thing you wrote, what was open
    hanging  an unsent draft, a note you left open, a question a task never closed, once you have moved on
    next     the open step of a task, while you are still on it
    link     two things that go together          (projects are offered through suggestions.py, as before)
    earlier  while you write: a line you saw or wrote before that goes with it (memory_search.earlier); a tap copies it
"""

import json
import os
import re
from datetime import datetime, timedelta

import config
import store
import tasks

KEEP_HOURS = 12
MAX_OPEN = 6
PER_KIND = {"earlier": 1, "resume": 1, "hanging": 3, "next": 3, "link": 2}
PRIORITY = ("earlier", "resume", "hanging", "next", "link")
TASK_DAYS = 3
FROM_MODEL = ("next", "link")
TEXT_CHARS = 300                 # kept in full for the detail card; the boxes shorten it themselves
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


def _add(doc, kind, text, ids, task, now, detail=None):
    text = tasks.clean(text, TEXT_CHARS)
    if not text or not ids:
        return None
    key = _key(kind, text)
    for step in doc["steps"]:
        if step["key"] == key:
            if step["state"] == "new":
                step.update(items=ids, task=task, seen=_iso(now), **({"detail": detail} if detail else {}))   # N2: refresh, never duplicate
            return None
    doc["n"] += 1
    step = {"id": f"n{doc['n']}", "key": key, "kind": kind, "text": text, "items": ids, "task": task,
            "state": "new", "made": _iso(now), "seen": _iso(now)}
    if detail:
        step["detail"] = detail
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
    surplus = []
    for kind, cap in PER_KIND.items():
        mine = sorted((s for s in waiting if s["kind"] == kind), key=lambda s: s["seen"], reverse=True)
        surplus += mine[cap:]
    rest = [s for s in waiting if s not in surplus]
    surplus += sorted(rest, key=lambda s: (-PRIORITY.index(s["kind"]) if s["kind"] in PRIORITY else 0, s["seen"]))[:max(len(rest) - MAX_OPEN, 0)]
    keep = [s for s in keep if s not in surplus]
    doc["steps"] = keep
    return repr(doc) != before


def view(doc, items, now=None):
    """What the pill draws: {"count", "steps": [{id, kind, text, task, things: [{app, title}], age}]}, newest first."""
    now = now or datetime.now()
    tidy(doc, items, now)
    rows = []
    order = sorted((s for s in doc["steps"] if s["state"] == "new"), key=lambda s: s["seen"], reverse=True)
    for step in sorted(order, key=lambda s: PRIORITY.index(s["kind"]) if s["kind"] in PRIORITY else 9):
        try:
            minutes = int((now - datetime.fromisoformat(step["seen"])).total_seconds() // 60)
        except ValueError:
            minutes = 0
        rows.append({"id": step["id"], "kind": step["kind"], "text": step["text"], "task": step.get("task"),
                     "detail": step.get("detail") or {},
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


# ---------------------------------------------------------------- resume and hanging: from what is stored, no model

def _when(iso):
    try:
        return datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


def _title(item):
    return tasks.clean(item.get("title") or item.get("doing") or "this", 60)


def _gap(draft=False):
    """How long away counts as left: RECALL_GAP_MINUTES (3 h), and a draft counts after a third of that (1 h)."""
    minutes = config.RECALL_GAP_MINUTES
    return timedelta(minutes=minutes / 3 if draft else minutes)


def recent_tasks(book, now):
    """Every task from the stored runs of the last TASK_DAYS days, newest run first: [(run time, task)]."""
    out = []
    for run in (book or {}).values():
        at = _when(run.get("at"))
        if at and now - at <= timedelta(days=TASK_DAYS):
            out += [(at, t) for t in run.get("tasks") or []]
    return sorted(out, key=lambda x: x[0], reverse=True)


def candidates(items, book, now, front_id=None):
    """Resume and hanging steps that are true right now: [(kind, text, item ids, task title, detail)]."""
    out = []
    seen_tasks = set()
    for at, t in recent_tasks(book, now):
        ids = [i for i in t.get("items", []) if i in items]
        if not ids or t.get("title") in seen_tasks:
            continue
        seen_tasks.add(t.get("title"))
        quiet = now - at >= _gap()
        if front_id and front_id in ids and quiet:
            detail = {k: t[k] for k in ("goal", "last_wrote", "open", "stage") if t.get(k)}
            detail["things"] = [{"app": items[i].get("app"), "title": _title(items[i])} for i in ids]
            out.append(("resume", f"Back to “{t['title']}”", ids, t["title"], detail))
        elif t.get("open") and front_id not in ids and quiet:
            newest = max((_when(items[i].get("last_seen")) or datetime.min for i in ids))
            if now - newest >= _gap():
                out.append(("hanging", f"Still open in “{t['title']}”: {t['open']}", ids[:2], t["title"], {}))
    for iid, item in items.items():
        if iid == front_id:
            continue
        seen = _when(item.get("last_seen"))
        if not seen:
            continue
        age = now - seen
        draft = item.get("state") or {}
        if item.get("kind") in ("writing_email", "composing_email") and (draft.get("draft") or draft.get("subject")) \
                and _gap(draft=True) <= age <= timedelta(days=TASK_DAYS):
            what = draft.get("subject") or draft.get("draft")
            out.append(("hanging", f"Unsent draft: “{tasks.clean(what, 70)}”", [iid], None, {}))
        elif age >= _gap() and age <= timedelta(days=TASK_DAYS):
            for note in notes_open(item)[:1]:
                out.append(("hanging", f"A note on “{_title(item)}”: {tasks.clean(note, 80)}", [iid], None, {}))
    return out


def earlier_candidate(found_earlier, items):
    """The refresh() tuple for memory_search.earlier(...), or None."""
    if not found_earlier or found_earlier.get("item") not in items:
        return None
    return ("earlier", f"“{tasks.clean(found_earlier['text'], 100)}”", [found_earlier["item"]], None,
            {"from": found_earlier["from"], "copy": found_earlier["text"]})


def notes_open(item):
    import notes
    return [n["text"] for n in notes.open_notes(item)]


def refresh(doc, items, book, now=None, front_id=None, extra=None):
    """Bring resume and hanging steps up to date: add what is true now, drop what no longer is (you came back to
    the note, you sent the draft). Steps from the model are untouched. `extra`: candidates worked out elsewhere (the
    "from earlier" one), kept in the same way. Returns the new steps."""
    now = now or datetime.now()
    keys, added = set(), []
    for kind, text, ids, task, detail in candidates(items, book, now, front_id) + list(extra or []):
        keys.add(_key(kind, tasks.clean(text, TEXT_CHARS)))
        step = _add(doc, kind, text, ids, task, now, detail)
        if step:
            added.append(step)
    doc["steps"] = [s for s in doc["steps"] if s["kind"] in FROM_MODEL or s.get("demo") or s["state"] != "new" or s["key"] in keys]
    tidy(doc, items, now)
    return [s for s in added if s in doc["steps"]]


def demo(doc, items, now=None):
    """`start --demo`: one step of each kind, with long text, so the pill's boxes and the full card can be tried at once.
    They are marked demo (refresh keeps them) and replaced on every start. Needs at least one thing; returns the steps."""
    now = now or datetime.now()
    doc["steps"] = [s for s in doc["steps"] if not s.get("demo")]
    ids = list(items)[:2]
    if not ids:
        return []
    things = [{"app": items[i].get("app"), "title": _title(items[i])} for i in ids]
    long = ("Check whether the Apps Script trigger really ran on the weekend, then compare the execution log with the "
            "scheduled folder in Gmail so you know which of the two is responsible for the emails that went out late")
    rows = [("resume", "Back to “Verify the follow-up automation”", {"goal": "Find out if the script, not Gmail, schedules the emails",
                                                                       "last_wrote": long, "open": "Compare the log with the Scheduled folder",
                                                                       "things": things}),
            ("hanging", "Still open in “Outreach tracker”: decide who gets the second reminder", {}),
            ("next", long, {}),
            ("earlier", "“The trigger runs the sendDrafts function every morning at eight o’clock”",
             {"from": "script.google.com · Auto Send · on screen · yesterday",
              "copy": "The trigger runs the sendDrafts function every morning at eight o’clock"})]
    out = []
    for kind, text, detail in rows:
        step = _add(doc, kind, text, ids, None, now, detail)
        if step:
            step["demo"] = True
            out.append(step)
    return out
