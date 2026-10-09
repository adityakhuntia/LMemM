#!/usr/bin/env python3
"""
LMemM - what happened between two screenshots of the same thing.

Works on pixels, so it works in any app: native, downloaded, browser tab,
canvas apps, games. Needs only the screenshots we already take, plus three
system counters (seconds since the last key press / scroll / click: never which
key) and where the pointer is at capture time.

    diff(prev_img, cur_img)               -> changed regions + scroll offset (pixels only)
    classify(change, prev_res, cur_res, inputs, pointer)
        -> {"category": "typing" | "reading" | "receiving" | "focus", ...}

    typing     you pressed keys and new text appeared in a changed region
    reading    the view scrolled, or nothing changed while you were on it
    receiving  new text appeared without any input from you (a message came in)
    focus      you clicked / pointed and that area changed (opening, switching, navigating)
"""

from difflib import SequenceMatcher

import re

import numpy as np
from PIL import Image

CELL = 16            # diff grid cell, in screenshot pixels
CELL_DIFF = 6.0      # mean abs grey-level difference for a cell to count as changed
MIN_CHANGE = 0.002   # below this share of changed cells, the frame is "unchanged"
SCROLL_MIN = 0.05    # share of cells changed before we test for a scroll

CHROME = {"tab", "address_bar", "bookmark", "menu_bar"}


def load(path):
    return np.asarray(Image.open(path).convert("L"), dtype=np.int16)


def _cells(a, b):
    h, w = (min(a.shape[0], b.shape[0]) // CELL) * CELL, (min(a.shape[1], b.shape[1]) // CELL) * CELL
    d = np.abs(a[:h, :w] - b[:h, :w]).reshape(h // CELL, CELL, w // CELL, CELL).mean(axis=(1, 3))
    return d > CELL_DIFF


def _regions(mask):
    """Merge touching changed cells into rectangles [x, y, w, h] in pixels."""
    seen = np.zeros_like(mask)
    out = []
    H, W = mask.shape
    for y in range(H):
        for x in range(W):
            if not mask[y, x] or seen[y, x]:
                continue
            stack, x0, y0, x1, y1 = [(y, x)], x, y, x, y
            seen[y, x] = True
            while stack:
                cy, cx = stack.pop()
                x0, y0, x1, y1 = min(x0, cx), min(y0, cy), max(x1, cx), max(y1, cy)
                for ny in range(cy - 1, cy + 2):           # 8-neighbours, 1-cell gap bridged
                    for nx in range(cx - 1, cx + 2):
                        if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
            out.append([x0 * CELL, y0 * CELL, (x1 - x0 + 1) * CELL, (y1 - y0 + 1) * CELL])
    return sorted(out, key=lambda r: -r[2] * r[3])


def _scroll(a, b, band):
    """Vertical shift that best maps a onto b inside the changed band, or 0."""
    x0, y0, w, h = band
    if h < 120:
        return 0
    # half resolution is plenty to find the offset, and 4x cheaper
    A, B = a[y0:y0 + h:2, x0:x0 + w:2], b[y0:y0 + h:2, x0:x0 + w:2]
    h = A.shape[0]
    base = np.abs(A - B).mean()
    best, best_dy = base, 0
    for dy in range(-min(200, h // 2), min(200, h // 2) + 1, 2):
        if dy == 0:
            continue
        if dy > 0:
            err = np.abs(A[dy:] - B[:-dy]).mean()
        else:
            err = np.abs(A[:dy] - B[-dy:]).mean()
        if err < best:
            best, best_dy = err, dy
    return best_dy * 2 if best < base * 0.35 else 0


def diff(prev, cur):
    """prev/cur: arrays from load(). Same window assumed."""
    if prev is None or prev.shape != cur.shape:
        return None
    mask = _cells(prev, cur)
    share = float(mask.mean())
    if share < MIN_CHANGE:
        return {"changed": 0.0, "regions": [], "scroll": 0}
    regions = _regions(mask)
    scroll = 0
    if share >= SCROLL_MIN:
        ys, xs = np.nonzero(mask)
        band = [int(xs.min()) * CELL, int(ys.min()) * CELL,
                int(xs.max() - xs.min() + 1) * CELL, int(ys.max() - ys.min() + 1) * CELL]
        scroll = _scroll(prev, cur, band)
    return {"changed": round(share, 4), "regions": regions[:12], "scroll": scroll}


def _hits(box, regions, pad=4):
    x, y, w, h = box
    return any(x < rx + rw + pad and rx - pad < x + w and y < ry + rh + pad and ry - pad < y + h
               for rx, ry, rw, rh in regions)


def _seen(text, before):
    """Was this line already on screen? Exact, or the same line re-read with OCR noise.
    A line that GREW ("Hi I am" -> "Hi I am testing") is new: that's typing."""
    if text in before:
        return True
    t = text.lower()
    if any(t.startswith(b.lower()) and len(t) >= len(b) + 2 for b in before if len(b) > 2):
        return False
    return any(SequenceMatcher(None, t, b.lower()).ratio() > 0.8 or
               (len(t) > 3 and (t in b.lower() or b.lower() in t) and abs(len(t) - len(b)) <= 3)
               for b in before)


def _near(objs, px, py):
    if px is None:
        return None
    best = None
    for o in objs:
        x, y, w, h = o["box"]
        dx = max(x - px, 0, px - (x + w))
        dy = max(y - py, 0, py - (y + h))
        d = (dx * dx + dy * dy) ** 0.5
        if d < 40 and (best is None or d < best[0]):
            best = (d, o)
    return best[1]["text"] if best else None


# UI words and status lines that are never content: input placeholders, presence,
# timestamps. Generic across apps.
NOISE = re.compile(
    r"^\W*(type a message|message|ask anything|ask .{0,20}|search.*|reply.*|write.*|"
    r"send a message|imessage|enter a prompt|how can i help.*|only admins can send messages|"
    r"online|typing\.*|last seen.*|today|yesterday|recent searches|clear all|"
    r"\d{1,2}[:.]\d{2}\s*(am|pm)?\W*\w{0,3}|\W*)\W*$", re.I)


def is_content(text):
    """Worth remembering as something read/typed/received: not UI noise, not a stray glyph."""
    return len(re.findall(r"[A-Za-z]", text)) >= 3 and not NOISE.match(text)


def _overlap(a, b):
    """Two boxes on the same spot of the screen (same row, overlapping horizontally)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return abs(ay - by) <= max(6, min(ah, bh)) and ax < bx + bw and bx < ax + aw


def _edits(objs, prev_objs):
    """Lines you EDITED: a line that grew ("Hi I" -> "Hi I am"), or new text sitting
    exactly where different text was before (placeholder -> your words). Text that
    simply appeared somewhere new (a message bubble, a list refreshing) is not an edit."""
    out = []
    for o in objs:
        t = o["text"]
        for p in prev_objs:
            if p["text"] == t:
                break
            grew = t.lower().startswith(p["text"].lower()) and len(t) >= len(p["text"]) + 2
            if grew or _overlap(o["box"], p["box"]):
                out.append(t)
                break
    return out


def classify(change, prev_res, cur_res, inputs, pointer, dt, kind=None):
    """
    change    diff() result, or None when there's no previous frame of this thing
    inputs    seconds since last key / scroll / click / any input (system counters)
    pointer   (x, y) in screenshot pixels, or None
    dt        seconds since the previous frame
    """
    objs = [o for o in cur_res["objects"] if o["text"] and o["kind"] not in CHROME]
    prev_objs = [o for o in prev_res["objects"] if o["text"] and o["kind"] not in CHROME] \
        if prev_res else []
    before = {o["text"] for o in prev_objs}
    regions = (change or {}).get("regions", [])
    typed = inputs["key"] < dt + 1
    scrolled = inputs["scroll"] < dt + 1
    clicked = inputs["click"] < dt + 1
    px, py = pointer or (None, None)
    at_pointer = _near(objs, px, py)

    out = {"category": None, "evidence": [], "new_text": [], "regions": regions[:5]}
    if change is None:
        # first look at this thing in this visit. What's already on screen (old messages,
        # earlier parts of a doc) isn't something you did now, so no text is recorded.
        out.update(category="reading", evidence=["opened it"])
        return out

    if change["scroll"] or (scrolled and change["regions"]):
        out["category"] = "reading"
        out["evidence"] = [f"scrolled {abs(change['scroll'])}px" if change["scroll"] else "scrolling"]
        out["new_text"] = [o["text"] for o in objs
                           if not _seen(o["text"], before) and is_content(o["text"])][:12]
        return out

    # new = in a changed region and not just the same line re-read slightly differently
    # (OCR flicker: "Library" vs "M Library")
    changed = [o for o in objs if _hits(o["box"], regions) and not _seen(o["text"], before)]
    new = [o["text"] for o in changed if is_content(o["text"])]
    if not regions:
        out.update(category="reading", evidence=["nothing changed"])
        return out
    edits = [t for t in _edits(changed, prev_objs) if is_content(t)]
    if typed and (edits or not new):
        out.update(category="typing", evidence=["keys pressed", "text edited in place"],
                   new_text=edits[:8])
    elif new and not (typed or clicked or scrolled):
        out.update(category="receiving", evidence=["new text appeared with no input from you"],
                   new_text=new[:8])
    else:
        out.update(category="focus",
                   evidence=["clicked" if clicked else "pointer", "that area changed"],
                   new_text=new[:6])
    if at_pointer:
        out["pointer_on"] = at_pointer
    return out
