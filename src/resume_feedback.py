"""LMemM - corrections to Resume: your word on a suggestion, kept apart from everything LMemM captured.

    right      "that's right"                      the suggestion stays, marked as confirmed by you
    outdated   "that's outdated / not what I meant"  the suggestion is not offered again
    replace    "use this instead"                  your text is offered instead, as yours
    exclude    "don't use this source"             the thing is left out of Resume (nothing is forgotten)

R34  Corrections are one small file of their own (resume_feedback.json). They never edit memory.json, a note or the
     trail, so deleting the file puts Resume back exactly as it was. A suggestion is matched by the source thing and
     its words (`key`), so an edited or new request is judged fresh.
"""

import hashlib
import json
import os
import re

import store

ACTIONS = ("right", "outdated", "replace", "exclude")


def key(item_id, text):
    words = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    return hashlib.sha1(f"{item_id}|{words}".encode()).hexdigest()[:12]


def empty():
    return {"version": 1, "steps": {}, "exclude": []}


def load(path):
    try:
        with open(path) as fh:
            doc = json.load(fh)
        return {**empty(), **doc}
    except (OSError, ValueError):
        return empty()


def record(fb, action, step_key=None, item_id=None, text=None, at=None):
    """Change `fb` (a dict from load()) and return it. Raises ValueError for anything it does not understand."""
    if action not in ACTIONS:
        raise ValueError(f"unknown correction: {action}")
    if action == "exclude":
        if not item_id:
            raise ValueError("exclude needs a thing")
        if item_id not in fb["exclude"]:
            fb["exclude"].append(item_id)
        return fb
    if not step_key:
        raise ValueError("this needs the suggestion it is about")
    if action == "replace" and not (text or "").strip():
        raise ValueError("replace needs your words")
    fb["steps"][step_key] = {"action": action, "at": at, **({"text": text.strip()} if action == "replace" else {})}
    return fb


def save(path, fb):
    store.write_json(path, fb)
