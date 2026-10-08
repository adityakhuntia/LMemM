"""LMemM - which memory item a screen belongs to: the same thing, or a new one.

One rule for every app. The ref (understand.py) names WHERE you are: a URL, a window,
a draft slot. A verified source id (a Google Doc's id) is authoritative. Otherwise
what you TYPED there tells instances apart:

  - same place, and your earlier text is still on screen      -> the same thing
  - same place, your text vanished while you stayed on it (no scroll), or you come
    back and the spot you typed into is empty                -> a NEW thing that just
    looks the same (a second email, a new note, a fresh prompt)
  - conversations (anything that received text from others) never split
  - new place reached without navigating, while what you typed is still on screen,
    or the old place only had a placeholder name ("new", "untitled")
                                                             -> the same thing, whose
    URL/id/title changed (a draft got saved, a doc got a name)
  - anything else is a different thing: two chats in one WhatsApp tab are two
"""

import hashlib
import re
from difflib import SequenceMatcher

import activity
import understand


def make_id(st, ref):
    return f'{st["kind"]}-{hashlib.sha1(ref.encode()).hexdigest()[:8]}'


def authored(item):
    """Did you type anything into this thing?"""
    return bool(item.get("activity", {}).get("typing", {}).get("text"))


def still_there(item, on_screen):
    """Is a real piece of what you typed into it still visible (exactly, re-read with
    OCR noise, or grown since)? Short fragments don't count: "magick" also matches a
    bookmark called "MagickWorld"."""
    typed = [t.lower() for t in item["activity"]["typing"]["text"][-6:]
             if len(t) >= 8 and activity.is_content(t)]
    screen = [l.lower() for l in on_screen if len(l) >= 8]
    return any(l.startswith(t) or SequenceMatcher(None, t, l).ratio() > 0.85
               for t in typed for l in screen)


def provisional(item):
    """A placeholder name the app gives something before it's saved or named."""
    return bool(re.search(r"(^|[:|/])(new|untitled)\b|\|$", item.get("ref") or "", re.I))


def conversation(item):
    """Anything that has received text from others is a stream (a chat, a thread)."""
    r = item["activity"]["receiving"]
    return bool(r["seconds"] or r.get("count"))


def is_empty_where_typed(item, res):
    """Coming back from elsewhere: is the spot you typed into (nearly) empty again?"""
    box = item.get("typing_area")
    if not box:
        return True
    x, y, w, h = box
    inside = [o for o in res["objects"] if o["text"] and len(re.findall(r"[A-Za-z]", o["text"])) >= 3
              and x - 10 <= o["box"][0] <= x + w + 10 and y - 10 <= o["box"][1] <= y + h + 10]
    return len(inside) <= 1


def resolve_item(items, st, cur, res, trigger, scrolled):
    """-> (item id, ref). `cur` is the open timeline event (or None). May re-key the
    current item in place when its place got a new name without you navigating."""
    ref = understand.ref(st)
    on_screen = [o["text"] for o in res["objects"]
                 if o["text"] and o["kind"] not in understand.CHROME]
    cur_item = items.get(cur["item"]) if cur else None

    instances = [i for i in items.values() if ref in i.get("refs", [i.get("ref")])]
    if st.get("stable_identity"):
        # Reuse existing IDs, including legacy items, without merging history.
        if instances:
            return max(instances, key=lambda i: i["last_seen"])["id"], ref
        return make_id(st, ref), ref
    if instances:
        for inst in sorted(instances, key=lambda i: i["last_seen"], reverse=True):
            if authored(inst) and still_there(inst, on_screen):
                return inst["id"], ref
        latest = max(instances, key=lambda i: i["last_seen"])
        if (authored(latest) and not scrolled and not conversation(latest)
                and (trigger == "timer" or is_empty_where_typed(latest, res))):
            return make_id(st, f"{ref}#{len(instances) + 1}"), ref   # your text is gone: a fresh one
        return latest["id"], ref

    if (cur_item and trigger == "timer" and cur_item["app"] == st["app"]
            and cur_item["kind"] == st["kind"]
            and (still_there(cur_item, on_screen)
                 or (provisional(cur_item) and not authored(cur_item)))):
        cur_item.setdefault("refs", [cur_item["ref"]]).append(ref)
        cur_item["ref"] = ref
        return cur_item["id"], ref
    return make_id(st, ref), ref


EMPTY_SCREEN = {"objects": [], "image_size": {"w": 1, "h": 1}}


def quick_state(meta, res=None):
    """What a screen with this metadata is, or None when that can't be told without
    reading the pixels. Without `res` only the URL, tab/window title and app are used,
    which is enough for pages, docs, AI chats, editors, terminals and most chat apps."""
    try:
        st = understand.describe(res or EMPTY_SCREEN, meta)
    except Exception:
        return None
    return st if st.get("target") else None


def find_item(items, st):
    """Id of the most recent item at the place `st` names, or None if you've never been there."""
    ref = understand.ref(st)
    seen = [i for i in items.values() if ref in i.get("refs", [i.get("ref")])]
    return max(seen, key=lambda i: i["last_seen"])["id"] if seen else None
