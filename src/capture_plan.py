"""LMemM - the pure parts of the capture path: no macOS here, so each rule is tested on any OS.

  windows_except_pid   which on-screen windows to put in a screenshot (everything but LMemM's own pill, cards and window)
  BrowserInfoCache     remember a browser tab's URL/title/private flag for a few seconds instead of asking the browser every capture
  Timings              the last N durations, for the p95 / max shown by `status` (how long the main loop blocks)
"""

import time
from collections import deque


def windows_except_pid(infos, pid):
    """Window numbers (front to back, as given) of everything on screen except one process's windows.
    `infos` is what CGWindowListCopyWindowInfo returns; entries without a number are skipped."""
    out = []
    for w in infos or []:
        number = w.get("kCGWindowNumber")
        if number is None or w.get("kCGWindowOwnerPID") == pid:
            continue
        out.append(int(number))
    return out


class BrowserInfoCache:
    """get(key, fetch): the cached value if it is younger than `ttl` seconds, else fetch() it.
    The key is (app, window id, window title): a tab switch changes the title, a new window changes the id,
    and a window is private or not for its whole life. A failed lookup (no URL) is never cached."""

    def __init__(self, ttl=10.0, clock=time.monotonic, max_entries=64):
        self.ttl, self.clock, self.max_entries = ttl, clock, max_entries
        self.data = {}
        self.hits = self.misses = 0

    def get(self, key, fetch):
        now = self.clock()
        hit = self.data.get(key)
        if hit is not None and now - hit[0] < self.ttl:
            self.hits += 1
            return hit[1]
        self.misses += 1
        value = fetch()
        if value and value[0]:
            self.data[key] = (now, value)
            if len(self.data) > self.max_entries:
                oldest = min(self.data, key=lambda k: self.data[k][0])
                del self.data[oldest]
        return value

    def forget(self):
        self.data.clear()


class Timings:
    """The most recent `size` durations in milliseconds."""

    def __init__(self, size=400):
        self.values = deque(maxlen=size)

    def add(self, ms):
        self.values.append(ms)

    def p95(self):
        if not self.values:
            return None
        ordered = sorted(self.values)
        return round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 1)

    def max(self):
        return round(max(self.values), 1) if self.values else None

    def count(self):
        return len(self.values)
