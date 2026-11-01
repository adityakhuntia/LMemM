"""Bounded local evidence from visible OCR text, without inferred decisions."""

import hashlib
import re

MAX_TEXT = 3000
MAX_EXCERPTS = 12
CONTENT_KINDS = {"heading", "paragraph", "text", "link"}
# menu bars and other UI chrome that slips past memory_content's content filter
CHROME_LINE = re.compile(
    r"^(?:file\s+edit\s+view|edit\s+view\s+insert|view\s+insert\s+format|"
    r"insert\s+format\s+tools)\b.*$|"
    r"^(?:file|edit|view|insert|format|tools|window|help|extensions|share|comment)"
    r"(?:\s+(?:file|edit|view|insert|format|tools|window|help|extensions|share|comment))+$", re.I)

DECISION = re.compile(
    r"^(?:decision\s*:|(?:we|i)\s+(?:have\s+)?(?:decided|chose|agreed|selected)\b)", re.I)


def visible_window_region(window, display):
    """Clip global CG window bounds to a display; return normalized x/y/w/h."""
    if not window or not display or display.get("Width", 0) <= 0 or display.get("Height", 0) <= 0:
        return None
    x = max(window["X"], display["X"])
    y = max(window["Y"], display["Y"])
    right = min(window["X"] + window["Width"], display["X"] + display["Width"])
    bottom = min(window["Y"] + window["Height"], display["Y"] + display["Height"])
    if right <= x or bottom <= y:
        return None
    return [(x - display["X"]) / display["Width"], (y - display["Y"]) / display["Height"],
            (right - x) / display["Width"], (bottom - y) / display["Height"]]


def extract_content(res, meta):
    """Keep readable lines fully inside the foreground window, excluding UI chrome.

    Older frames have no window region. Do not attribute their entire display
    to the foreground app; they still support the existing activity rules.
    """
    region = meta.get("window_region")
    if not region:
        return None
    width, height = res["image_size"]["w"], res["image_size"]["h"]
    x, y, w, h = [region[0] * width, region[1] * height,
                   region[2] * width, region[3] * height]
    lines, seen = [], set()
    remaining = MAX_TEXT
    for obj in res["objects"]:
        if obj["kind"] not in CONTENT_KINDS or obj.get("conf", 0) < 0.5:
            continue
        bx, by, bw, bh = obj["box"]
        if bx < x or by < y or bx + bw > x + w or by + bh > y + h:
            continue
        text = re.sub(r"\s+", " ", obj.get("text") or "").strip()
        if len(text) < 12 or len(re.findall(r"\w+", text)) < 3 or text in seen:
            continue
        seen.add(text)
        text = text[:remaining]
        if not text:
            break
        lines.append(text)
        remaining -= len(text) + 1
        if remaining <= 0:
            break
    if not lines:
        return None
    return {"text": "\n".join(lines),
            "decision_quotes": [line for line in lines if DECISION.search(line) and "?" not in line][:5],
            "observed_at": meta["iso"],
            "source": {"app": meta.get("app"), "window": meta.get("window"), "url": meta.get("url")}}


def remember_content(item, capture):
    """Append distinct evidence, refresh repeat timestamps, and bound history.

    Return whether the latest text changed, so the tracker can refresh its screenshot
    even when a document's title and other selected state fields stay the same.
    """
    if not capture:
        return False
    content = item.setdefault("content", {"version": 1, "excerpts": []})
    excerpts = content["excerpts"]
    normalized = re.sub(r"\s+", " ", capture["text"]).strip()
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    for index, excerpt in enumerate(excerpts):
        if excerpt["id"] == digest:
            changed = index != len(excerpts) - 1
            excerpt["last_seen"] = capture["observed_at"]
            # Retain the most recently revisited evidence when history fills.
            excerpts.append(excerpts.pop(index))
            return changed
    excerpts.append({"id": digest, "text": capture["text"], "source": capture["source"],
                     "first_seen": capture["observed_at"], "last_seen": capture["observed_at"],
                     "decision_quotes": capture["decision_quotes"]})
    del excerpts[:-MAX_EXCERPTS]
    return True
