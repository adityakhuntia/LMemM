"""LMemM - how long screenshots are kept.

Each thing keeps one thumbnail. It is deleted `SCREENSHOT_DAYS` after it was taken, unless
the thing is pinned or has an open note (those keep theirs for as long as that holds).
Only the picture goes: the text, activity, notes and timeline of the thing are untouched.
"""

import os
import re
from datetime import datetime, timedelta

import config
import notes

NAME = re.compile(r"^(\d{8}-\d{6})\.jpg$")


def taken_at(image):
    """When a kept screenshot was taken, from its file name (YYYYMMDD-HHMMSS.jpg)."""
    m = NAME.match(image or "")
    return datetime.strptime(m.group(1), "%Y%m%d-%H%M%S") if m else None


def expire_screenshots(items, now=None, days=None):
    """Delete screenshots older than `days` (default SCREENSHOT_DAYS). Returns how many."""
    now = now or datetime.now()
    cutoff = now - timedelta(days=config.SCREENSHOT_DAYS if days is None else days)
    data_dir, removed = config.paths().data_dir, 0
    for item in items.values():
        image = item.get("screenshot")
        when = taken_at(image)
        if when is None or when >= cutoff or item.get("pinned") or notes.open_notes(item):
            continue
        for name in (image, image[:-4] + ".json"):
            try:
                os.remove(os.path.join(data_dir, name))
            except OSError:
                pass
        item["screenshot"] = None
        item["screenshot_expired"] = now.isoformat(timespec="seconds")
        removed += 1
    return removed
