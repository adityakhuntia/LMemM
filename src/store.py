"""LMemM - persistence. Three files, nothing else.

    data/memory/memory.json          every thing LMemM remembers, across all sessions
    data/memory/sessions/<id>.json   one session's timeline: when you were on what
    data/memory/context/<id>.json    a clean export of one session for handing to an AI (context.py)

memory.json carries two views of the same items in one file: "things" (what a person
would read - see `readable`) and "items" (everything, including the bookkeeping the
tracker needs - refs, content hashes, typing areas - to keep identity and resurfacing
working). Open notes-by-project (what `notes done` used to need a separate pending.json
for) is computed on demand from "items"; nothing reads a stored copy, so there isn't one.

Writes are atomic (temp file + rename). Schema 3; every newer field is additive.
"""

import json
import os
from collections import Counter
from datetime import datetime

import config
import notes

SCHEMA = 3
CATEGORIES = ("typing", "reading", "receiving", "focus")


def write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    os.replace(path + ".tmp", path)


def _migrate_split_items(memory_dir):
    """Before schema 3, the full items lived in a separate .index.json next to the
    readable memory.json. Read it once; save_memory() folds everything into one file
    and clears the old ones out the next time it runs."""
    legacy = os.path.join(memory_dir, ".index.json")
    if not os.path.exists(legacy):
        return None
    with open(legacy) as fh:
        return json.load(fh).get("items")


def nice_time(iso):
    return iso.replace("T", " ")[:16] if iso else None


def duration(s):
    s = int(s or 0)
    return f"{s // 3600}h {s % 3600 // 60}m" if s >= 3600 else f"{s // 60}m {s % 60}s" if s >= 60 else f"{s}s"


def mostly(acts):
    secs = {c: a["seconds"] for c, a in acts.items() if a.get("seconds")}
    return max(secs, key=secs.get) if secs else None


# ---------------------------------------------------------------- load

def load_items():
    """Every remembered thing, by id. Raises ValueError rather than silently starting empty."""
    from input_store import recover_deletion
    p = config.paths()
    recover_deletion(p.memory_dir)
    src = p.items_file
    if not os.path.exists(src):
        return {}
    try:
        with open(src) as fh:
            doc = json.load(fh)
        if not isinstance(doc, dict):
            raise ValueError("memory.json is not a JSON object")
        if not isinstance(doc.get("items"), list):
            doc["items"] = _migrate_split_items(p.memory_dir)      # pre-schema-3 layout
        if not isinstance(doc.get("items"), list):
            raise ValueError("memory.json is missing its full item list ('items'); "
                             "a readable-only copy isn't enough to resume from")
        if doc.get("schema_version", 1) not in (1, 2, SCHEMA):
            raise ValueError("unsupported memory schema version")
        items = {i["id"]: i for i in doc["items"]}
        if len(items) != len(doc["items"]):
            raise ValueError("duplicate stored item IDs")
        for i in items.values():          # entries written before activity tracking existed
            i.setdefault("activity", {c: {"seconds": 0, "text": []} for c in CATEGORIES})
            i.setdefault("mostly", None)
        return items
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(f"Cannot load memory from {src}: {error}") from error


# ---------------------------------------------------------------- readable views

def readable(i):
    """One memory entry as a person would want to read it."""
    acts = {}
    for c, a in i.get("activity", {}).items():
        if not a.get("seconds") and not a.get("text"):
            continue
        entry = {"time": duration(a.get("seconds"))}
        if a.get("count"):
            entry["times"] = a["count"]
        if a.get("text"):
            entry["text"] = a["text"][-8:]
        acts[c] = entry
    out = {"id": i["id"], "app": i["app"], "project": notes.project_of(i),
           "what": i.get("title") or i["doing"], "doing": i["doing"]}
    if i.get("notes"):
        out["your_notes"] = [{"id": notes.note_id(n), "at": nice_time(n["at"]), "text": n["text"],
                              "status": "done" if notes.is_done(i, n) else "open"} for n in i["notes"]]
    if i.get("content"):
        out["content"] = i["content"]
    latest = {k: v for k, v in (i.get("state") or {}).items() if v != out["what"]}
    if latest:                                   # e.g. an email's to / subject / draft
        out["latest"] = latest
    if acts:
        out["mostly"] = i.get("mostly")
        out["activity"] = acts
    out["time"] = {"total": duration(i["seconds"]), "visits": i["visits"],
                   "first": nice_time(i["first_seen"]), "last": nice_time(i["last_seen"])}
    if i.get("screenshot"):                       # gone once its retention has passed
        out["screenshot"] = i["screenshot"]
    if i.get("pinned"):
        out["pinned"] = True
    return out


def session_doc(session, events, notes):
    by_app = Counter()
    for e in events:
        by_app[e["app"]] += e["seconds"]
    return {
        "schema_version": SCHEMA,
        "session": session,
        "seconds_by_app": dict(by_app.most_common()),
        "time_by_app": {a: duration(s) for a, s in by_app.most_common()},
        "timeline": [{"from": e["from"], "to": e["to"], "for": duration(e["seconds"]),
                      "seconds": e["seconds"], "item": e["item"],
                      "activity": e.get("activity", {}), "trigger": e.get("trigger"),
                      "app": e["app"], "doing": e["doing"],
                      **({"mostly": e["mostly"]} if e.get("mostly") else {}),
                      **({"resurfaced": e["resurfaced"]} if e.get("resurfaced") else {}),
                      "memory": e["item"]} for e in events],
        **({"notes": [{**n, "on": n["item"]} for n in notes]} if notes else {}),
    }


# ---------------------------------------------------------------- the user

_USER = {"path": None, "value": None}


def load_user():
    """The "user" block of memory.json (who this is, from first-run setup), or None. Read once
    per data directory, then kept: save_memory() writes it back every time, so the tracker
    never has to re-read the whole file for it."""
    path = config.paths().items_file
    if _USER["path"] != path:
        value = None
        try:
            with open(path) as fh:
                doc = json.load(fh)
            if isinstance(doc, dict) and isinstance(doc.get("user"), dict):
                value = doc["user"]
        except (OSError, ValueError):
            pass
        _USER["path"], _USER["value"] = path, value
    return _USER["value"]


def save_user(user):
    """Write the "user" block into memory.json, leaving everything else in the file as it is
    (or creating the file when there is none yet). An unreadable file is never overwritten:
    ValueError, so a damaged memory is not replaced by a nearly empty one."""
    if not isinstance(user, dict):
        raise ValueError("user must be an object")
    path = config.paths().items_file
    doc = None
    if os.path.exists(path):
        try:
            with open(path) as fh:
                doc = json.load(fh)
        except (OSError, ValueError) as error:
            raise ValueError(f"Cannot update {path}: {error}") from error
        if not isinstance(doc, dict):
            raise ValueError(f"Cannot update {path}: not a JSON object")
    if doc is None:
        doc = {"schema_version": SCHEMA, "updated": nice_time(datetime.now().isoformat(timespec="seconds")),
               "things": [], "items": []}
    doc["user"] = user
    write_json(path, doc)
    _USER["path"], _USER["value"] = path, user


# ---------------------------------------------------------------- save

def save_memory(items):
    """Write the one memory file: the readable view first, the full items after. Clears
    out any pre-schema-3 .index.json / pending.json left over from before they merged."""
    memory_dir = config.paths().memory_dir
    ordered = sorted(items.values(), key=lambda i: i["last_seen"], reverse=True)
    write_json(config.paths().items_file, {
        "schema_version": SCHEMA,
        "updated": nice_time(datetime.now().isoformat(timespec="seconds")),
        **({"user": load_user()} if load_user() else {}),
        "things": [readable(i) for i in ordered],
        "items": ordered,
    })
    for stale in (".index.json", "pending.json"):
        try:
            os.remove(os.path.join(memory_dir, stale))
        except OSError:
            pass


def save_session(session, events, notes):
    write_json(os.path.join(config.paths().sessions_dir, session + ".json"),
               session_doc(session, events, notes))
