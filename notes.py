"""LMemM - your notes (⌃⌥N) on the things you work on.

A note is written for whatever was in front when you pressed the hotkey. The
screenshot taken at that moment is resolved in the background, so a note may wait
("pending") until OCR says which memory item that screen is; it is never guessed
onto the previous item.
"""


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
