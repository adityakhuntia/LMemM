"""LMemM - persistence. Where memory lives on disk and how it reads.

    data/memory/.index.json          full internal state, one entry per thing (source of truth)
    data/memory/memory.json          the same, as a person would read it
    data/memory/pending.json         open notes (pending edits), grouped by project
    data/memory/sessions/<id>.json   one session's timeline: when you were on what

Writes are atomic (temp file + rename). Schema 2; every newer field is additive.
"""

import json
import os
from collections import Counter
from datetime import datetime

import config
import notes

SCHEMA = 2
CATEGORIES = ("typing", "reading", "receiving", "focus")


def write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    os.replace(path + ".tmp", path)


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
    src = p.index_file if os.path.exists(p.index_file) else p.items_file
    if not os.path.exists(src):
        return {}
    try:
        with open(src) as fh:
            doc = json.load(fh)
        if not isinstance(doc, dict) or not isinstance(doc.get("items"), list):
            raise ValueError("missing full internal items; restore .index.json rather than replacing readable memory")
        if doc.get("schema_version", 1) not in (1, SCHEMA):
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


# ---------------------------------------------------------------- save

def save_memory(items):
    """Write the index (source of truth) and the two readable views of it."""
    p = config.paths()
    ordered = sorted(items.values(), key=lambda i: i["last_seen"], reverse=True)
    write_json(p.index_file, {"schema_version": SCHEMA, "items": ordered})
    write_json(p.items_file, {"schema_version": SCHEMA,
                              "updated": nice_time(datetime.now().isoformat(timespec="seconds")),
                              "things": [readable(i) for i in ordered]})
    write_json(p.pending_file, notes.pending_view(items))


def save_session(session, events, notes):
    write_json(os.path.join(config.paths().sessions_dir, session + ".json"),
               session_doc(session, events, notes))
