"""LMemM - the event trail on disk: one JSON line per event, one file per day, 48 hours.

Appends are buffered (no write per event, so no stall on the capture path) and flushed every
second or 50 events. Old events are deleted whole: a day file that ends before the cutoff is
removed; the file that straddles it is rewritten without the old lines. Files are 0600 in a 0700
folder. "Forget" removes the last N minutes, one app, or everything.
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import config


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def parse(ts):
    return datetime.fromisoformat(ts)


class TrailStore:
    def __init__(self, root=None, session="s", retention_hours=None, clock=None, max_mb=None):
        self.root = root or config.paths().trail_dir
        self.session = session
        self.retention = timedelta(hours=config.TRAIL_RETENTION_HOURS if retention_hours is None else retention_hours)
        if self.retention <= timedelta(0):
            raise ValueError("retention must be positive")
        self.max_bytes = int((config.TRAIL_MAX_MB if max_mb is None else max_mb) * 1024 * 1024)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.lock = threading.Lock()
        self.buf = []
        self.seq = 0
        self.last_flush = time.monotonic()
        os.makedirs(self.root, mode=0o700, exist_ok=True)

    # ---- writing

    def add(self, kind, **fields):
        """Record one event. Returns it."""
        with self.lock:
            self.seq += 1
            ev = {"t": iso(self.clock()), "seq": self.seq, "session": self.session, "kind": kind}
            ev.update({k: v for k, v in fields.items() if v is not None})
            self.buf.append(ev)
            if len(self.buf) >= 50 or time.monotonic() - self.last_flush >= 1.0:
                self._flush()
            return ev

    def flush(self):
        with self.lock:
            self._flush()

    def _flush(self):
        self.last_flush = time.monotonic()
        by_day = {}
        for ev in self.buf:
            by_day.setdefault(ev["t"][:10], []).append(ev)
        self.buf = []
        for day, evs in by_day.items():
            path = os.path.join(self.root, day + ".jsonl")
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as fh:
                fh.write("".join(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n" for e in evs))

    # ---- reading

    def files(self):
        try:
            return sorted(f for f in os.listdir(self.root) if f.endswith(".jsonl") and len(f) == 16)
        except OSError:
            return []

    def read(self, since=None, kinds=None, limit=None, include_expired=False):
        """Events oldest first. Events older than the retention window are never returned."""
        self.flush()
        floor = self.clock() - self.retention
        out = []
        for name in self.files():
            try:
                with open(os.path.join(self.root, name), encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            ev = json.loads(line)
                            ts = parse(ev["t"])
                        except (ValueError, KeyError):
                            continue                   # a torn last line after a crash
                        if (not include_expired and ts < floor) or (since and ts < since):
                            continue
                        if kinds and ev["kind"] not in kinds:
                            continue
                        out.append(ev)
            except OSError:
                continue
        out.sort(key=lambda e: (e["t"], e.get("seq", 0)))
        return out[-limit:] if limit else out

    # ---- deleting

    def sweep(self):
        """Delete everything past the retention window and enforce the size cap. -> events removed."""
        self.flush()
        cutoff = self.clock() - self.retention
        removed = 0
        for name in self.files():
            path = os.path.join(self.root, name)
            day_end = datetime.fromisoformat(name[:10]).replace(tzinfo=timezone.utc) + timedelta(days=1)
            if day_end <= cutoff:
                removed += self._count(path)
                os.remove(path)
            elif day_end - timedelta(days=1) < cutoff:
                removed += self._rewrite(path, lambda ev: parse(ev["t"]) >= cutoff)
        files = self.files()
        while files and self._size() > self.max_bytes and len(files) > 1:
            path = os.path.join(self.root, files.pop(0))
            removed += self._count(path)
            os.remove(path)
        return removed

    def forget(self, minutes=None, app=None, everything=False):
        """Delete the last `minutes`, every event of one app (bundle id or name), or all. -> removed."""
        self.flush()
        if everything:
            n = sum(self._count(os.path.join(self.root, f)) for f in self.files())
            for f in self.files():
                os.remove(os.path.join(self.root, f))
            return n
        since = self.clock() - timedelta(minutes=minutes) if minutes else None
        removed = 0
        for name in self.files():
            def keep(ev):
                hit_time = since is None or parse(ev["t"]) >= since
                hit_app = app is None or app in (ev.get("bundle_id"), ev.get("app"), (ev.get("place") or {}).get("app"))
                return not (hit_time and hit_app)
            removed += self._rewrite(os.path.join(self.root, name), keep)
        return removed

    def _size(self):
        return sum(os.path.getsize(os.path.join(self.root, f)) for f in self.files())

    @staticmethod
    def _count(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return sum(1 for _ in fh)
        except OSError:
            return 0

    @staticmethod
    def _rewrite(path, keep):
        kept, dropped = [], 0
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        ok = keep(json.loads(line))
                    except (ValueError, KeyError):
                        ok = False
                    if ok:
                        kept.append(line)
                    else:
                        dropped += 1
        except OSError:
            return 0
        if not dropped:
            return 0
        if kept:
            tmp = path + ".tmp"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.writelines(kept)
            os.replace(tmp, path)
        else:
            os.remove(path)
        return dropped
