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
    """Open notes to remind you of when you come back to this item, or []."""
    pending = open_notes(item)
    last = item.get("resurfaced_at")
    if not pending or (last and _seconds_between(last, now_iso) < cooldown):
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
