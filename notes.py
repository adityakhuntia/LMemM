"""LMemM - your notes (⌃⌥N) on the things you work on.

A note is written for whatever was in front when you pressed the hotkey. The
screenshot taken at that moment is resolved in the background, so a note may wait
("pending") until OCR says which memory item that screen is; it is never guessed
onto the previous item.

Every note is a pending edit until marked done; it resurfaces when you come back
to the thing it's on, and `lmemm.py notes` shows all open ones by project.
"""

import hashlib
from datetime import datetime


def record(items, frame_item, session_notes, target, text, at):
    """Store a note. `target` is ("frame", capture ts) or ("item", item id).
    Returns the item it landed on, or None if it is still waiting for its frame."""
    kind, key = target
    item_id = frame_item.get(key) if kind == "frame" else key
    item = items.get(item_id)
    note = {"at": at, "text": text}
    if item:
        note["while"] = item["doing"]
        item.setdefault("notes", []).append(note)
        item["last_seen"] = max(item["last_seen"], at)
    status = ("attached" if item else
              "pending" if kind == "frame" and key not in frame_item else "unresolved")
    session_notes.append({"item": item["id"] if item else None, **note,
                          "frame": key if kind == "frame" else None, "status": status})
    return item


def attach_pending(items, frame_item, session_notes):
    """Attach notes whose frame has now been resolved to an item."""
    for note in session_notes:
        if note.get("status") != "pending":
            continue
        item = items.get(frame_item.get(note.get("frame")))
        if item is not None:
            item.setdefault("notes", []).append({"at": note["at"], "text": note["text"], "while": item["doing"]})
            item["last_seen"] = max(item["last_seen"], note["at"])
            note.update(item=item["id"], status="attached")


def fail_pending(session_notes, frame_ts):
    """The frame a note was waiting for could not be resolved."""
    for note in session_notes:
        if note.get("frame") == frame_ts and note.get("status") == "pending":
            note["status"] = "unresolved"


# ---------------------------------------------------------------- notes as pending edits
#
# Every note is a pending edit until you mark it done. Done-state lives in
# item["notes_done"] = {note id: when}, never inside the note itself: the provenance
# store matches notes by value, so a note must not change after it is written.

GROUPS = {"email_draft": "Email", "email": "Email", "mailbox": "Email", "email_search": "Email",
          "chat": "Chats", "chat_list": "Chats", "ai_conversation": "AI chats"}


def note_id(note):
    """Stable id derived from the note, so notes written before ids existed get one too."""
    return "n-" + hashlib.sha1(f'{note["at"]}|{note["text"]}'.encode()).hexdigest()[:6]


def is_done(item, note):
    return note_id(note) in item.get("notes_done", {})


def open_notes(item):
    return [n for n in item.get("notes", []) if not is_done(item, n)]


def project_of(item):
    """Where an item belongs in the project view."""
    state = item.get("state") or {}
    if item.get("kind") == "code_file" and state.get("project"):
        return state["project"]
    if item.get("kind") == "document":
        return item.get("title") or state.get("document") or item["app"]
    return GROUPS.get(item.get("kind"), item["app"])


def set_done(items, ids, done=True, at=None):
    """Mark notes (by id) done or open again. Returns the ids that were found."""
    at = at or datetime.now().isoformat(timespec="seconds")
    wanted, found = set(ids), []
    for item in items.values():
        for n in item.get("notes", []):
            nid = note_id(n)
            if nid not in wanted:
                continue
            found.append(nid)
            marks = item.setdefault("notes_done", {})
            if done:
                marks.setdefault(nid, at)
            else:
                marks.pop(nid, None)
            if not marks:
                item.pop("notes_done")
    return found


def due_for_resurfacing(item, now_iso, cooldown):
    """Open notes to remind you of when you come back to this item, or []. A note you
    added since the last reminder always shows next time; otherwise at most once per
    `cooldown` seconds."""
    pending = open_notes(item)
    last = item.get("resurfaced_at")
    if not pending:
        return []
    if last and _seconds_between(last, now_iso) < cooldown and not any(n["at"] > last for n in pending):
        return []
    return pending


def _seconds_between(a, b):
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()


def pending_view(items, include_done=False):
    """Open notes grouped project -> item, most recent first. Also written to pending.json."""
    projects = {}
    for item in items.values():
        shown = item.get("notes", []) if include_done else open_notes(item)
        if not shown:
            continue
        entry = {"id": item["id"], "app": item["app"], "what": item.get("title") or item["doing"],
                 "last_seen": item["last_seen"][:16].replace("T", " "),
                 "notes": [{"id": note_id(n), "at": n["at"][:16].replace("T", " "), "text": n["text"],
                            **({"done": item["notes_done"][note_id(n)][:16].replace("T", " ")}
                               if is_done(item, n) else {})}
                           for n in sorted(shown, key=lambda n: n["at"], reverse=True)]}
        projects.setdefault(project_of(item), []).append(entry)
    ordered = []
    for name, entries in projects.items():
        entries.sort(key=lambda e: e["notes"][0]["at"], reverse=True)
        ordered.append({"project": name,
                        "open": sum(1 for e in entries for n in e["notes"] if "done" not in n),
                        "items": entries})
    ordered.sort(key=lambda p: p["items"][0]["notes"][0]["at"], reverse=True)
    return {"updated": datetime.now().isoformat(timespec="seconds").replace("T", " ")[:16],
            "open": sum(p["open"] for p in ordered), "projects": ordered}


def card(items, item_id):
    """What the on-screen widget shows for the thing in front: the edits left on its
    project (this thing's first), and the project's plan: every note, open then done,
    plus its history (notes written / ticked off, newest first)."""
    item = items.get(item_id)
    if item is None:
        return None
    project = project_of(item)
    members = [i for i in items.values() if project_of(i) == project]
    left, plan, history = [], [], []
    for i in sorted(members, key=lambda i: (i["id"] != item_id, i["last_seen"]), reverse=False):
        what = i.get("title") or i["doing"]
        for n in i.get("notes", []):
            nid = note_id(n)
            done_at = i.get("notes_done", {}).get(nid)
            row = {"id": nid, "text": n["text"], "at": n["at"], "on": what,
                   "here": i["id"] == item_id, "done": done_at}
            plan.append(row)
            if not done_at:
                left.append(row)
            history.append({"at": n["at"], "event": "added", "text": n["text"], "on": what})
            if done_at:
                history.append({"at": done_at, "event": "done", "text": n["text"], "on": what})
    left.sort(key=lambda r: (not r["here"], r["at"]))
    plan.sort(key=lambda r: (bool(r["done"]), r["at"]))
    history.sort(key=lambda h: h["at"], reverse=True)
    return {"title": item.get("title") or item["doing"], "app": item["app"], "project": project,
            "left": left, "plan": plan, "history": history,
            "things": len(members), "visits": sum(i.get("visits", 0) for i in members),
            "seconds": sum(i.get("seconds", 0) for i in members)}


def pill_summary(data):
    """(open notes on the thing in front, text of the first one) for the pill itself.
    Notes on other things in the project don't light the pill: it is about *here*."""
    here = [n for n in (data or {}).get("left", []) if n["here"]]
    return len(here), (here[0]["text"] if here else "")


def card_view(data, mode="here", show_done=False, fading=()):
    """What the pill's card draws, as plain data (widget.py only turns it into views).

    mode "here": the open notes on this thing, plus how many more wait elsewhere in the project.
    mode "project": every open note on the project grouped by thing, with the done ones
    behind a "Done · N" row. `fading` holds note ids ticked a moment ago: they stay on
    screen struck through for a beat instead of vanishing under the cursor."""
    if data is None:
        return {"empty": True}
    fading = set(fading)
    shown = [n for n in data["plan"] if not n["done"] or n["id"] in fading]
    row = lambda n: {"id": n["id"], "text": n["text"], "done": bool(n["done"])}
    if mode == "project":
        groups = {}
        for n in sorted(shown, key=lambda n: not n["here"]):
            groups.setdefault(n["on"], []).append(row(n))
        done = [row(n) for n in data["plan"] if n["done"] and n["id"] not in fading]
        return {"mode": "project", "title": data["project"], "caption": f"{len(data['left'])} open",
                "back": data["title"], "groups": list(groups.items()),
                "done": done if show_done else [], "done_count": len(done)}
    return {"mode": "here", "title": data["title"], "caption": data["app"],
            "rows": [row(n) for n in shown if n["here"]],
            "more": sum(1 for n in data["left"] if not n["here"]), "project": data["project"]}
