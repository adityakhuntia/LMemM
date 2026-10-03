#!/usr/bin/env python3
"""
LMemM - object resolver (proof of concept).

Takes the frames logger.py writes into ./data and resolves each screenshot
into a structured list of on-screen objects: tabs, address bar, bookmarks,
sidebar items, buttons, headings, text, panels - each with its text, its box
and what it contains (emails, links, phone numbers, dates, people).

Everything runs on-device through Apple's Vision framework (the same OCR
Live Text uses). No model download, nothing leaves the machine.

    python3 resolver.py                  # resolve every frame not yet resolved
    python3 resolver.py 20260926-181010  # one frame (ts or path), prints it
    python3 resolver.py --watch          # follow the logger, resolve as frames land
    python3 resolver.py --annotate       # also draw boxes into data/annotated/
    python3 resolver.py --force          # redo frames already resolved
    python3 resolver.py --report         # data/report.html: timeline of everything resolved

Writes data/objects/<ts>.json. Kept out of data/*.json on purpose, so
peek.py and run.sh keep counting only logger frames.
"""

import glob
import json
import os
import re
import sys
import time
from collections import Counter

try:
    import objc
    import Foundation
except ImportError:
    sys.exit("Missing dependency. Run:  pip3 install pyobjc-framework-Cocoa")


# ---------------------------------------------------------------- config

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUT_DIR = os.path.join(DATA_DIR, "objects")
ANNOT_DIR = os.path.join(DATA_DIR, "annotated")
FAST_OCR = False        # True = Vision's fast mode: ~3x quicker, worse on small text
MIN_TEXT_CONF = 0.3     # drop OCR lines below this
WATCH_POLL = 2          # seconds between checks in --watch

BROWSERS = {
    "Google Chrome", "Google Chrome Canary", "Brave Browser",
    "Microsoft Edge", "Arc", "Safari",
}

# placeholder text inside an empty input field
INPUT_RE = re.compile(r"^(?:\W{1,3}|[QO] )?\s?(search|type a|type your|enter|write|ask|message|reply to|add a)\b", re.I)

# words that, alone or leading a short label, almost always mean a control
BUTTON_WORDS = {
    "reply", "forward", "send", "cancel", "save", "submit", "compose", "join",
    "share", "book", "ok", "done", "next", "back", "continue", "sign", "log",
    "login", "open", "close", "delete", "edit", "new", "add", "create", "run",
    "upload", "download", "accept", "decline", "allow", "deny", "apply",
    "search", "learn", "test", "more", "view", "show", "copy", "start", "stop",
}


# ---------------------------------------------------------------- vision

_VN = {}


def vision():
    """Load Vision.framework through pyobjc-core (no extra pip package)."""
    if not _VN:
        objc.loadBundle("Vision", _VN,
                        bundle_path="/System/Library/Frameworks/Vision.framework")
    return _VN


def run_vision(path, w, h):
    """
    OCR lines, rectangle regions and scene labels for one image.
    Boxes come back as [x, y, w, h] in image pixels, top-left origin.
    """
    vn = vision()
    url = Foundation.NSURL.fileURLWithPath_(path)
    handler = vn["VNImageRequestHandler"].alloc().initWithURL_options_(url, {})

    ocr = vn["VNRecognizeTextRequest"].alloc().init()
    ocr.setRecognitionLevel_(1 if FAST_OCR else 0)      # 0 accurate, 1 fast
    ocr.setUsesLanguageCorrection_(not FAST_OCR)

    rects = vn["VNDetectRectanglesRequest"].alloc().init()
    rects.setMaximumObservations_(0)                    # no cap
    rects.setMinimumSize_(0.015)
    rects.setMinimumAspectRatio_(0.05)
    rects.setMinimumConfidence_(0.6)

    scene = vn["VNClassifyImageRequest"].alloc().init()

    if not handler.performRequests_error_([ocr, rects, scene], None):
        raise RuntimeError(f"Vision failed on {path}")

    def px(b):
        # Vision: normalised, bottom-left origin -> pixels, top-left origin
        return [round(b.origin.x * w), round((1 - b.origin.y - b.size.height) * h),
                round(b.size.width * w), round(b.size.height * h)]

    lines = []
    for o in ocr.results() or []:
        c = o.topCandidates_(1)
        if not c:
            continue
        c = c[0]
        if c.confidence() < MIN_TEXT_CONF or not c.string().strip():
            continue
        lines.append({"text": c.string().strip(), "conf": round(c.confidence(), 2),
                      "box": px(o.boundingBox())})

    boxes = [px(o.boundingBox()) for o in rects.results() or []]
    labels = [{"label": o.identifier(), "conf": round(o.confidence(), 2)}
              for o in scene.results() or [] if o.confidence() > 0.1][:8]
    return lines, boxes, labels


# ---------------------------------------------------------------- geometry

def area(b):
    return b[2] * b[3]


def contains(outer, inner, slack=3):
    return (outer[0] - slack <= inner[0] and outer[1] - slack <= inner[1]
            and inner[0] + inner[2] <= outer[0] + outer[2] + slack
            and inner[1] + inner[3] <= outer[1] + outer[3] + slack)


def cy(b):
    return b[1] + b[3] / 2


def dist(b, x, y):
    """Distance from a point to a box (0 if inside)."""
    dx = max(b[0] - x, 0, x - (b[0] + b[2]))
    dy = max(b[1] - y, 0, y - (b[1] + b[3]))
    return (dx * dx + dy * dy) ** 0.5


# ---------------------------------------------------------------- entities

ENTITY_RES = {
    "email": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    "url": re.compile(r"\b(?:https?://)?(?:[\w-]+\.)+(?:com|org|net|io|ai|dev|edu|gov|in|co|app|me)\b(?:/[^\s,)]*)?", re.I),
    "phone": re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)"),
    "time": re.compile(r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm|AM|PM)\b|\b\d{1,2}:\d{2}\b"),
    "date": re.compile(
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?"
        r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}"
        r"|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    "money": re.compile(r"(?:[$€£₹]\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s?(?:USD|INR|EUR|Rs\.?))"),
    "path": re.compile(r"(?<![\w./:])(?:~|\.{1,2})?/(?:[\w.-]+/)+[\w.-]+"),
}

NOT_NAMES = {
    "The", "This", "That", "More", "New", "Google", "Inbox", "Search", "Sent",
    "Drafts", "Starred", "Snoozed", "Labels", "Categories", "Meeting", "Join",
    "Book", "Learn", "Test", "Share", "Reply", "Forward", "Cancel", "Mail",
    "Chat", "Meet", "All", "Your", "You", "Project", "Hosted", "Booked",
}


def entities(text):
    found = {}
    for kind, rx in ENTITY_RES.items():
        hits = [m.group(0).strip() for m in rx.finditer(text)]
        if kind == "url":       # an email's domain is not a separate link
            hits = [u for u in hits if not re.search(re.escape(u) + r"$", " ".join(found.get("email", [])))]
            hits = [u for u in hits if "@" not in u]
        if kind == "phone":     # skip things that are really dates/ids
            hits = [p for p in hits if sum(ch.isdigit() for ch in p) >= 9
                    and not re.search(r"\d{8}-\d{6}", p)]     # our own frame timestamps
        if hits:
            found[kind] = hits
    # person: a whole line that is 2-3 capitalised words, optionally "- role"
    head = re.split(r"\s+[-–(]", text)[0].strip()
    words = head.split()
    if (2 <= len(words) <= 3 and all(re.fullmatch(r"[A-Z][a-z]+", w) for w in words)
            and not set(words) & NOT_NAMES):
        found["person"] = [head]
    return found


# ---------------------------------------------------------------- resolve

CHROME_KINDS = {"tab", "address_bar", "bookmark", "menu_bar", "button"}


def classify(lines, rects, meta, img_w, img_h):
    """Give every OCR line a kind, and pull panels out of the rectangles."""
    objs = []
    heights = sorted(l["box"][3] for l in lines) or [10]
    median_h = heights[len(heights) // 2]
    is_browser = meta.get("app") in BROWSERS
    url = meta.get("url") or ""
    host = re.sub(r"^https?://", "", url).split("/")[0]

    # browser chrome: find the address bar line, everything above it is tabs,
    # the row right below it is the bookmarks bar
    addr = None
    if is_browser:
        cands = [l for l in lines if cy(l["box"]) < img_h * 0.15 and
                 (("://" in l["text"]) or (host and host in l["text"]))]
        addr = min(cands, key=lambda l: l["box"][1], default=None)
    addr_top = addr["box"][1] if addr else None
    addr_bot = addr["box"][1] + addr["box"][3] if addr else None

    # left rail: short lines stacked at the same x in the left 20%
    left_x = Counter(round(l["box"][0] / 6) for l in lines
                     if l["box"][0] < img_w * 0.2 and len(l["text"].split()) <= 4)
    rail_cols = {k for k, n in left_x.items() if n >= 4}

    # rectangles that tightly wrap a short line -> that line is a button
    small_rects = [r for r in rects if area(r) < img_w * img_h * 0.02]

    for l in lines:
        b, t = l["box"], l["text"]
        words = t.split()
        first = re.sub(r"[^a-z]", "", words[0].lower()) if words else ""
        kind = None

        if addr is not None and l is addr:
            kind = "address_bar"
        elif addr is not None and cy(b) < addr_top:
            kind = "tab"
        elif addr is not None and addr_bot < cy(b) < addr_bot + 3.5 * median_h:
            kind = "bookmark"
        elif not is_browser and cy(b) < img_h * 0.03:
            kind = "menu_bar"
        elif round(b[0] / 6) in rail_cols and len(words) <= 4:
            kind = "sidebar_item"
        else:
            tight = any(contains(r, b) and area(r) < 4 * area(b) + 400 for r in small_rects)
            if INPUT_RE.match(t) and len(words) <= 6:
                kind = "input"
            elif (len(words) <= 4 and not entities(t)
                    and (tight or (first in BUTTON_WORDS and len(words) <= 3))):
                kind = "button"
            elif b[3] >= 1.35 * median_h and len(words) <= 16:
                kind = "heading"
            elif len(words) >= 8:
                kind = "paragraph"
            else:
                kind = "text"

        o = {"kind": kind, "text": t, "box": b, "conf": l["conf"]}
        ents = entities(t)
        if kind in CHROME_KINDS:    # a bookmark called "Gates Scholarship" is not a person
            ents.pop("person", None)
        if ents:
            o["entities"] = ents
            if kind in ("text", "paragraph") and len(words) <= 3 and ({"email", "url"} & ents.keys()):
                o["kind"] = "link"
        objs.append(o)

    # panels: big rectangles that hold several text objects (cards, dialogs, panes)
    panels = []
    for r in sorted(rects, key=area, reverse=True):
        if area(r) < img_w * img_h * 0.02:
            continue
        inside = [o for o in objs if contains(r, o["box"])]
        if len(inside) >= 3:
            panels.append({"kind": "panel", "text": None, "box": r, "conf": 1.0,
                           "children": len(inside)})
    return objs, panels


def resolve(meta_path):
    with open(meta_path) as f:
        meta = json.load(f)
    img_path = os.path.join(DATA_DIR, meta["image"])
    if not os.path.exists(img_path):
        raise FileNotFoundError(img_path)

    w, h = image_size(img_path)
    t0 = time.time()
    lines, rects, labels = run_vision(img_path, w, h)
    objs, panels = classify(lines, rects, meta, w, h)

    # reading order, then ids; panels first so children can point at them
    objs.sort(key=lambda o: (round(o["box"][1] / 8), o["box"][0]))
    everything = panels + objs
    for i, o in enumerate(everything):
        o["id"] = i
    for o in objs:
        holders = [p for p in panels if contains(p["box"], o["box"])]
        if holders:
            o["parent"] = min(holders, key=lambda p: area(p["box"]))["id"]

    # cursor is logged in screen points; frames are downscaled pixels
    scale = w / meta["screen"]["w"] if meta.get("screen") else 1
    focus = None
    if meta.get("cursor") and objs:
        cx, cyy = meta["cursor"]["x"] * scale, meta["cursor"]["y"] * scale
        near = min(objs, key=lambda o: dist(o["box"], cx, cyy))
        d = dist(near["box"], cx, cyy)
        if d < 60:
            focus = {"id": near["id"], "kind": near["kind"], "text": near["text"],
                     "distance_px": round(d)}

    ents = {}
    for o in objs:
        for k, vs in o.get("entities", {}).items():
            for v in vs:
                ents.setdefault(k, [])
                if v not in ents[k]:
                    ents[k].append(v)

    return {
        "ts": meta["ts"],
        "image": meta["image"],
        "image_size": {"w": w, "h": h},
        "px_per_point": round(scale, 4),
        "context": {
            "app": meta.get("app"),
            "site": re.sub(r"^https?://", "", meta.get("url") or "").split("/")[0] or None,
            "title": meta.get("tab_title") or meta.get("window"),
        },
        "scene": labels,
        "counts": dict(Counter(o["kind"] for o in everything)),
        "focus": focus,
        "entities": ents,
        "objects": everything,
        "resolver": {"engine": "apple-vision", "fast": FAST_OCR,
                     "seconds": round(time.time() - t0, 2)},
    }


def image_size(path):
    """Pixel size without needing Pillow."""
    from AppKit import NSBitmapImageRep
    rep = NSBitmapImageRep.imageRepWithContentsOfFile_(path)
    return int(rep.pixelsWide()), int(rep.pixelsHigh())


def add_delta(res, prev):
    """What text appeared / vanished since the previous frame."""
    if prev is None:
        return
    now = [o["text"] for o in res["objects"] if o["text"]]
    before = [o["text"] for o in prev["objects"] if o["text"]]
    added = [t for t in now if t not in set(before)]           # reading order
    removed = [t for t in before if t not in set(now)]
    res["delta"] = {
        "prev": prev["ts"],
        "same_as_prev": not added and not removed,
        "added": len(added),
        "removed": len(removed),
        "added_text": added[:25],
    }


# ---------------------------------------------------------------- output

COLORS = {
    "tab": "#8e44ad", "address_bar": "#2980b9", "bookmark": "#16a085",
    "menu_bar": "#7f8c8d", "input": "#1abc9c", "sidebar_item": "#d35400", "button": "#e74c3c",
    "heading": "#f1c40f", "paragraph": "#95a5a6", "text": "#bdc3c7",
    "link": "#3498db", "panel": "#2ecc71",
}


def annotate(res):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("  (skip --annotate: pip3 install pillow)")
        return
    img = Image.open(os.path.join(DATA_DIR, res["image"])).convert("RGB")
    d = ImageDraw.Draw(img)
    for o in res["objects"]:
        x, y, w, h = o["box"]
        c = COLORS.get(o["kind"], "#ffffff")
        d.rectangle([x, y, x + w, y + h], outline=c, width=1 if o["kind"] == "panel" else 2)
        if o["kind"] != "panel":
            d.text((x, max(0, y - 10)), o["kind"], fill=c)
    if res.get("focus"):
        f = next(o for o in res["objects"] if o["id"] == res["focus"]["id"])
        x, y, w, h = f["box"]
        d.rectangle([x - 4, y - 4, x + w + 4, y + h + 4], outline="#ff00ff", width=3)
    os.makedirs(ANNOT_DIR, exist_ok=True)
    img.save(os.path.join(ANNOT_DIR, res["ts"] + ".jpg"), quality=80)


def show(res):
    c = res["context"]
    print(f"{res['ts']}  {c['app']}  {c['site'] or ''}  {res['resolver']['seconds']}s")
    print(f"  title    {c['title']}")
    print(f"  scene    {', '.join(l['label'] for l in res['scene'][:4])}")
    print(f"  objects  " + "  ".join(f"{k}={v}" for k, v in sorted(res["counts"].items())))
    if res.get("focus"):
        print(f"  focus    [{res['focus']['kind']}] {res['focus']['text']}")
    for k, vs in res["entities"].items():
        print(f"  {k:8} {' | '.join(vs[:6])}{' ...' if len(vs) > 6 else ''}")
    if "delta" in res:
        dl = res["delta"]
        change = "UNCHANGED" if dl["same_as_prev"] else f"+{dl['added']} / -{dl['removed']} lines"
        print(f"  delta    {change} vs {dl['prev']}")


def out_path(ts):
    return os.path.join(OUT_DIR, ts + ".json")


def load_out(ts):
    try:
        with open(out_path(ts)) as f:
            return json.load(f)
    except Exception:
        return None


def frames():
    """Logger frames (meta json) in time order."""
    return sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))


def process(meta_paths, force=False, do_annotate=False, verbose=True):
    os.makedirs(OUT_DIR, exist_ok=True)
    all_ts = [os.path.basename(p)[:-5] for p in frames()]
    done = 0
    for p in meta_paths:
        ts = os.path.basename(p)[:-5]
        if not force and os.path.exists(out_path(ts)):
            continue
        try:
            res = resolve(p)
        except Exception as e:
            print(f"  ! {ts}: {e}")
            continue
        i = all_ts.index(ts) if ts in all_ts else -1
        add_delta(res, load_out(all_ts[i - 1]) if i > 0 else None)
        with open(out_path(ts), "w") as f:
            json.dump(res, f, indent=1, ensure_ascii=False)
        if do_annotate:
            annotate(res)
        if verbose:
            show(res)
            print()
        done += 1
    return done


# ---------------------------------------------------------------- report

REPORT_CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1f;--mute:#6e6e73;--line:#e3e3e0;--chip:#eef1f6;--accent:#2f6fde}
@media (prefers-color-scheme:dark){:root{--bg:#141415;--card:#1e1e20;--fg:#ececee;--mute:#9a9aa0;--line:#2e2e32;--chip:#2a2f3a;--accent:#7aa7ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 -apple-system,system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}h1{font-size:22px;margin:0 0 4px}
.mute{color:var(--mute)}.stats{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 24px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.stat b{display:block;font-size:20px}.sec{margin:28px 0 10px;font-size:15px}
.frame{display:grid;grid-template-columns:260px 1fr;gap:16px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:10px}
.frame img{width:100%;border-radius:6px;border:1px solid var(--line);display:block}
.frame h3{margin:0 0 2px;font-size:14px}.chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}
.chip{background:var(--chip);border-radius:6px;padding:1px 7px;font-size:12px;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chip i{color:var(--mute);font-style:normal;margin-right:4px}
.same{font-size:12px;color:var(--mute);padding:4px 12px 12px}
details summary{cursor:pointer;color:var(--accent);font-size:12px;margin-top:6px}
details ul{margin:6px 0 0;padding-left:18px;font-size:12px}
@media (max-width:700px){.frame{grid-template-columns:1fr}}
"""


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def report(since=None, path=None):
    """HTML timeline of resolved frames (from `since` on, if given). Returns its path."""
    rows = [r for r in (load_out(os.path.basename(p)[:-5]) for p in frames()
                        if not since or os.path.basename(p)[:-5] >= since) if r]
    if not rows:
        print("nothing resolved yet. Run:  python3 lmemm.py")
        return None

    apps = Counter(r["context"]["site"] or r["context"]["app"] or "?" for r in rows)
    unchanged = sum(1 for r in rows if r.get("delta", {}).get("same_as_prev"))
    ents = {}
    for r in rows:
        for k, vs in r["entities"].items():
            c = ents.setdefault(k, Counter())
            for v in vs:
                c[v] += 1

    def iso(ts):
        return f"{ts[9:11]}:{ts[11:13]}:{ts[13:15]}"

    h = [f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
         f"<title>LMemM Session Report</title><style>{REPORT_CSS}</style><main>",
         f"<h1>What the resolver saw</h1><div class=mute>{iso(rows[0]['ts'])} to {iso(rows[-1]['ts'])}"
         f" on {rows[0]['ts'][:4]}-{rows[0]['ts'][4:6]}-{rows[0]['ts'][6:8]}</div>",
         "<div class=stats>"]
    for label, val in [("frames", len(rows)),
                       ("unchanged", f"{unchanged} ({100 * unchanged // max(len(rows), 1)}%)"),
                       ("objects / frame", sum(len(r["objects"]) for r in rows) // len(rows)),
                       ("sec / frame", round(sum(r["resolver"]["seconds"] for r in rows) / len(rows), 2))]:
        h.append(f"<div class=stat><b>{esc(val)}</b><span class=mute>{label}</span></div>")
    h.append("</div><h2 class=sec>Where the time went</h2><div class=chips>")
    for a, n in apps.most_common(12):
        h.append(f"<span class=chip>{esc(a)} <i>{n}</i></span>")
    h.append("</div><h2 class=sec>Things it picked up across the session</h2>")
    for k in ("person", "email", "url", "date", "time", "phone", "money", "path"):
        if k in ents:
            h.append(f"<div class=chips><span class=chip><i>{k}</i></span>")
            for v, n in ents[k].most_common(15):
                h.append(f"<span class=chip>{esc(v)}{f' <i>×{n}</i>' if n > 1 else ''}</span>")
            h.append("</div>")

    h.append("<h2 class=sec>Timeline</h2>")
    skipped = 0
    for r in rows:
        if r.get("delta", {}).get("same_as_prev"):
            skipped += 1
            continue
        if skipped:
            h.append(f"<div class=same>… {skipped} unchanged frame(s)</div>")
            skipped = 0
        c = r["context"]
        img = f"annotated/{r['ts']}.jpg" if os.path.exists(os.path.join(ANNOT_DIR, r["ts"] + ".jpg")) else r["image"]
        heads = [o["text"] for o in r["objects"] if o["kind"] == "heading"][:3]
        h.append(f"<div class=frame><a href='{img}'><img loading=lazy src='{img}'></a><div>"
                 f"<h3>{iso(r['ts'])} · {esc(c['site'] or c['app'] or '?')}</h3>"
                 f"<div class=mute>{esc(c['title'] or '')}</div><div class=chips>")
        if r.get("focus"):
            h.append(f"<span class=chip><i>cursor on {r['focus']['kind']}</i>{esc(r['focus']['text'])}</span>")
        for t in heads:
            h.append(f"<span class=chip><i>heading</i>{esc(t)}</span>")
        for k, vs in r["entities"].items():
            for v in vs[:4]:
                h.append(f"<span class=chip><i>{k}</i>{esc(v)}</span>")
        h.append("</div>")
        if "delta" in r:
            d = r["delta"]
            h.append(f"<details><summary>+{d['added']} / −{d['removed']} lines since {iso(d['prev'])}</summary><ul>"
                     + "".join(f"<li>{esc(t)}</li>" for t in d["added_text"]) + "</ul></details>")
        counts = "  ".join(f"{k} {v}" for k, v in sorted(r["counts"].items()))
        h.append(f"<div class=mute style='font-size:12px;margin-top:6px'>{esc(counts)}</div></div></div>")
    if skipped:
        h.append(f"<div class=same>… {skipped} unchanged frame(s)</div>")
    h.append("</main>")

    path = path or os.path.join(DATA_DIR, "report.html")
    with open(path, "w") as f:
        f.write("".join(h).replace("src='", f"src='{os.path.relpath(DATA_DIR, os.path.dirname(path))}/")
                .replace("href='", f"href='{os.path.relpath(DATA_DIR, os.path.dirname(path))}/"))
    print(f"wrote {path}")
    return path


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    ann = "--annotate" in sys.argv

    if args:
        paths = []
        for a in args:
            ts = os.path.basename(a).split(".")[0]
            p = os.path.join(DATA_DIR, ts + ".json")
            if not os.path.exists(p):
                sys.exit(f"no logger frame {ts} in {DATA_DIR}")
            paths.append(p)
        process(paths, force=True, do_annotate=ann)
        return

    if "--report" in sys.argv:
        report()
        return

    if "--watch" in sys.argv:
        sys.stdout.reconfigure(line_buffering=True)     # readable when piped / nohup'd
        print(f"LMemM resolver watching {DATA_DIR}  (Ctrl-C to stop)\n")
        while True:
            process(frames(), force=False, do_annotate=ann)
            time.sleep(WATCH_POLL)

    n = process(frames(), force=force, do_annotate=ann)
    print(f"resolved {n} frame(s) -> {OUT_DIR}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped.")
