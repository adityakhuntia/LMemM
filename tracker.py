#!/usr/bin/env python3
"""
LMemM - event-driven capture. Screenshots when something changes, not on a clock.

    START
      watch: app switch (macOS notification), window / tab title change,
             new front window (popups), lock / unlock, sleep / wake, display sleep
    ON trigger      wait SETTLE s for the screen to settle (debounce) -> CAPTURE
    EVERY s         same window, nothing triggered -> CAPTURE
    idle > IDLE s, locked, asleep, skip-listed app/site -> paused, no capture
    PIN (SIGUSR1)   -> CAPTURE marked pinned (always its own event)

    CAPTURE   skip-list check -> screenshot of the display the window is on -> queue
    RESOLVER  (own thread; capture never waits for it)
              resolve -> what is the user doing (understand.py)
              same app + action + target as the current event -> extend it, delete the frame
              anything else -> close the current event, start a new one, keep its frame

Output: data/memory/<session>.json, a timeline of what you did:
    {"app": "Gmail", "action": "writing_email", "doing": "Writing an email to ...",
     "from": "22:06:23", "to": "22:06:33", "seconds": 10, "details": {...}, ...}

Everything here is cheap: app switches arrive as NSWorkspace notifications,
and the window/tab check is one CGWindowList call (~0.2 ms) every POLL seconds.
No keyboard or cursor tracking; idle time comes from the system's own
"seconds since last input" counter.

Run it through lmemm.py:   python3 lmemm.py          (Ctrl-C to stop)
Pin the current screen:    python3 lmemm.py pin
"""

import hashlib
import json
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime

try:
    import objc
    import Foundation
    from AppKit import NSEvent, NSObject, NSScreen, NSWorkspace
except ImportError:
    sys.exit("Missing dependency. Run:  pip3 install pyobjc-framework-Cocoa")

import activity
import dictation
import resolver
import understand


# ---------------------------------------------------------------- config

EVERY = 5               # seconds between captures while nothing else happens
SETTLE = 1.0            # debounce: wait this long after the last trigger
MAX_SETTLE = 3.0        # ...but never longer than this after the first one
MIN_GAP = 2.0           # never two captures closer than this (pinned excepted)
POLL = 0.5              # seconds between window/tab title checks
IDLE = 60               # no input for this long -> pause
MAX_QUEUE = 8           # resolver backlog above which timer captures are skipped
SCALE_PX = 1280         # downscale screenshots to this long edge

DATA_DIR = resolver.DATA_DIR
MEMORY_DIR = os.path.join(DATA_DIR, "memory")
PIDFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".lmemm.pid")

BROWSERS = resolver.BROWSERS
CHROMIUM = {"Google Chrome", "Google Chrome Canary", "Brave Browser", "Microsoft Edge", "Arc"}

# never captured: password managers, private windows, banking / payment sites
SKIP_APPS = {
    "com.1password.1password", "com.agilebits.onepassword7", "com.bitwarden.desktop",
    "com.apple.keychainaccess", "com.apple.Passwords", "com.lastpass.LastPass",
    "com.dashlane.dashlanephonefinal", "org.keepassxc.keepassxc", "com.nordpass.macos.NordPass",
}
SKIP_SITES = re.compile(
    r"bank|netbanking|onlinesbi|hdfc|icici|axisbank|kotak|paypal\.|wise\.com|stripe\.com"
    r"|razorpay\.com/(app|dashboard)|paytm|phonepe|zerodha|groww|coinbase|binance"
    r"|accounts\.google\.com|appleid\.apple\.com|/login|/signin|password", re.I)
# frontmost while the screen is locked or the screensaver runs
LOCK_APPS = {"loginwindow", "ScreenSaverEngine"}
SKIP_TITLES = re.compile(r"private browsing|incognito|inprivate|password", re.I)


# ---------------------------------------------------------------- macOS hooks

_CG = {}


def cg():
    if not _CG:
        b = objc.loadBundle("CoreGraphics", {},
                            bundle_path="/System/Library/Frameworks/CoreGraphics.framework")
        objc.loadBundleFunctions(b, _CG, [
            ("CGWindowListCopyWindowInfo", b"@II"),
            ("CGEventSourceSecondsSinceLastEventType", b"dII"),
            ("CGPreflightScreenCaptureAccess", b"Z"),
            ("CGRequestScreenCaptureAccess", b"Z"),
        ])
    return _CG


def idle_seconds(event_type=0xFFFFFFFF):
    # HID system state; default = any input event type
    return cg()["CGEventSourceSecondsSinceLastEventType"](1, event_type)


def input_ages():
    """Seconds since the last key press, scroll, and click. Counters only: never
    which key, never where you clicked."""
    return {
        "key": round(idle_seconds(10), 1),                                  # keyDown
        "scroll": round(idle_seconds(22), 1),                               # scrollWheel
        "click": round(min(idle_seconds(1), idle_seconds(3)), 1),           # left/right mouseDown
    }


def pointer_on(display_frame):
    """Pointer position at capture, in points from the captured display's top-left."""
    p = NSEvent.mouseLocation()
    f = display_frame
    x, y = p.x - f.origin.x, (f.origin.y + f.size.height) - p.y
    if 0 <= x < f.size.width and 0 <= y < f.size.height:
        return {"x": int(x), "y": int(y)}
    return None


def front():
    """Frontmost app + its front window: name, bundle id, pid, window id, title, bounds."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        return None
    pid = app.processIdentifier()
    win = None
    # on-screen windows, front to back, desktop excluded
    for w in cg()["CGWindowListCopyWindowInfo"](1 | 16, 0) or []:
        if w.get("kCGWindowOwnerPID") != pid or w.get("kCGWindowLayer") != 0:
            continue
        b = w.get("kCGWindowBounds") or {}
        if b.get("Height", 0) < 80 or b.get("Width", 0) < 80:
            continue
        win = w
        break
    b = dict(win.get("kCGWindowBounds")) if win else None
    return {
        "app": app.localizedName(),
        "bundle_id": app.bundleIdentifier(),
        "pid": pid,
        "win_id": win.get("kCGWindowNumber") if win else None,
        "window": (win.get("kCGWindowName") or None) if win else None,
        "bounds": b,
    }


_SCRIPTS = {}


def browser_info(app):
    """URL, tab title, private? for the front tab. In-process AppleScript, compiled once."""
    if app not in BROWSERS:
        return None, None, False
    if app not in _SCRIPTS:
        if app == "Safari":
            src = 'tell application "Safari" to get {URL, name} of front document'
        elif app in CHROMIUM:
            src = (f'tell application "{app}" to get {{URL, title}} of active tab of front window'
                   f' & {{mode of front window}}')
        else:
            return None, None, False
        _SCRIPTS[app] = Foundation.NSAppleScript.alloc().initWithSource_(src)
    res, err = _SCRIPTS[app].executeAndReturnError_(None)
    if res is None:
        return None, None, False
    vals = [res.descriptorAtIndex_(i).stringValue() for i in range(1, res.numberOfItems() + 1)]
    url, title = vals[0], vals[1] if len(vals) > 1 else None
    private = len(vals) > 2 and vals[2] == "incognito"
    return url, title, private


def display_for(bounds):
    """1-based screencapture -D index of the display holding the window's centre."""
    screens = NSScreen.screens()
    if not bounds or len(screens) < 2:
        return 1, screens[0].frame()
    main_h = screens[0].frame().size.height
    cx = bounds["X"] + bounds["Width"] / 2
    cy = main_h - (bounds["Y"] + bounds["Height"] / 2)      # CG top-left -> Cocoa bottom-left
    for i, s in enumerate(screens):
        f = s.frame()
        if f.origin.x <= cx < f.origin.x + f.size.width and f.origin.y <= cy < f.origin.y + f.size.height:
            return i + 1, f
    return 1, screens[0].frame()


def screenshot(path, display):
    subprocess.run(["screencapture", "-x", "-o", "-t", "jpg", "-D", str(display), path],
                   check=False)
    if os.path.exists(path):
        subprocess.run(["sips", "-Z", str(SCALE_PX), path], capture_output=True, check=False)


# ---------------------------------------------------------------- system events

class Events(NSObject):
    """Receives NSWorkspace / distributed notifications on the main run loop."""

    def initWithTracker_(self, t):
        self = objc.super(Events, self).init()
        self.t = t
        return self

    def appSwitched_(self, note):
        self.t.trigger("app_switch")

    def willSleep_(self, note):
        self.t.set_flag("asleep", True)

    def didWake_(self, note):
        self.t.set_flag("asleep", False)

    def screensSlept_(self, note):
        self.t.set_flag("display_off", True)

    def screensWoke_(self, note):
        self.t.set_flag("display_off", False)

    def locked_(self, note):
        self.t.set_flag("locked", True)

    def unlocked_(self, note):
        self.t.set_flag("locked", False)


def subscribe(events):
    nc = NSWorkspace.sharedWorkspace().notificationCenter()
    for sel, name in [
        ("appSwitched:", "NSWorkspaceDidActivateApplicationNotification"),
        ("willSleep:", "NSWorkspaceWillSleepNotification"),
        ("didWake:", "NSWorkspaceDidWakeNotification"),
        ("screensSlept:", "NSWorkspaceScreensDidSleepNotification"),
        ("screensWoke:", "NSWorkspaceScreensDidWakeNotification"),
    ]:
        nc.addObserver_selector_name_object_(events, sel, name, None)
    dc = Foundation.NSDistributedNotificationCenter.defaultCenter()
    dc.addObserver_selector_name_object_(events, "locked:", "com.apple.screenIsLocked", None)
    dc.addObserver_selector_name_object_(events, "unlocked:", "com.apple.screenIsUnlocked", None)


# ---------------------------------------------------------------- tracker

def hms(ts):
    return f"{ts[9:11]}:{ts[11:13]}:{ts[13:15]}"


def say(msg):
    print(msg, flush=True)


def line(t, app, msg):
    """Every live line looks the same: time, app, what happened."""
    say(f"{t}  {(app or '')[:14]:14}  {msg}")


def quiet_system_logs():
    """macOS input-method frameworks NSLog noise ("IMKClient subclass", "_TIPropertyValueIsValid",
    ...) straight to the terminal whenever a text box gets focus. Send the raw stderr file
    descriptor to /dev/null, but keep Python's own errors visible on the real one."""
    try:
        real = os.dup(2)
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
        sys.stderr = os.fdopen(real, "w", buffering=1)
    except OSError:
        pass


class Tracker:
    def __init__(self, every=EVERY):
        self.every = every
        self.flags = {"asleep": False, "display_off": False, "locked": False}
        self.pending = None            # (trigger, due, first_seen)
        self.pin = False
        self.last_sig = None
        self.last_capture = 0.0
        self.last_poll = 0.0
        self.paused = None
        self.q = queue.Queue()
        self.events = []               # the session timeline: when, pointing at items
        self.last_frame = None         # previous frame (pixels + OCR) for change tracking
        self.lock = threading.Lock()   # the resolver thread and the note window both write memory
        self.note_request = False
        self.panel = dictation.NotePanel()
        self.notes = []                # this session's dictated notes
        self.frame_item = {}           # screenshot ts -> memory entry it became
        self.last_ts = None
        self.items = load_items()      # the memory: one entry per thing, across sessions
        self.stats = Counter()
        self.session = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.running = True

    # -- events in

    def trigger(self, why):
        now = time.time()
        if self.pending:
            first = self.pending[2]
            due = min(now + SETTLE, first + MAX_SETTLE)
            self.pending = (self.pending[0] if self.pending[0] == "app_switch" else why, due, first)
        else:
            self.pending = (why, now + SETTLE, now)

    def set_flag(self, k, v):
        self.flags[k] = v
        if not v:
            self.trigger("wake")

    # -- main loop

    def tick(self):
        if self.panel.open:
            self.panel.poll()           # starts Dictation once the window is really in front
            return                      # you're dictating: don't capture the note window
        if self.note_request:
            self.note_request = False
            self.open_note()
            return
        now = time.time()
        f = front()

        reason = next((k for k, v in self.flags.items() if v), None)
        if reason is None and f and f["app"] in LOCK_APPS:
            reason = "locked"
        if reason is None and self.pin:          # a pin wakes us even when idle
            self.pin = False
            self.capture("pin", pinned=True)
            return
        if reason is None and idle_seconds() > IDLE:
            reason = "idle"
        if reason:
            if self.paused != reason:
                line(datetime.now().strftime("%H:%M:%S"), "", f"paused ({reason})")
                self.paused = reason
            self.pending = None
            return
        if self.paused:
            line(datetime.now().strftime("%H:%M:%S"), "", "resumed")
            self.paused = None
            self.trigger("resume")

        if now - self.last_poll >= POLL:
            self.last_poll = now
            sig = f
            if sig and self.last_sig:
                if sig["pid"] != self.last_sig["pid"]:
                    self.trigger("app_switch")
                elif sig["win_id"] != self.last_sig["win_id"]:
                    self.trigger("window_change")
                elif sig["window"] != self.last_sig["window"]:
                    self.trigger("tab_change" if sig["app"] in BROWSERS else "title_change")
            self.last_sig = sig or self.last_sig

        if self.pending and now >= self.pending[1]:
            if now - self.last_capture >= MIN_GAP:
                why = self.pending[0]
                self.pending = None
                self.capture(why)
        elif now - self.last_capture >= self.every:
            if self.q.qsize() < MAX_QUEUE:
                self.capture("timer")
            else:
                self.last_capture = now
                self.stats["backlog_skip"] += 1

    def capture(self, trigger, pinned=False):
        self.last_capture = time.time()
        f = front()
        if f is None:
            return
        url, tab_title, private = browser_info(f["app"])
        site = re.sub(r"^https?://", "", url or "").split("/")[0] or None
        title = tab_title or f["window"]

        skip = ("password manager" if f["bundle_id"] in SKIP_APPS
                else "private window" if private or SKIP_TITLES.search(title or "")
                else "sensitive site" if url and SKIP_SITES.search(url)
                else None)
        if skip:
            self.stats["skipped"] += 1
            line(datetime.now().strftime("%H:%M:%S"), f["app"], f"skipped: {skip}")
            return

        display, frame = display_for(f["bounds"])
        size = frame.size
        inputs, pointer = input_ages(), pointer_on(frame)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        img = os.path.join(DATA_DIR, ts + ".jpg")
        if os.path.exists(img):          # two captures in one second
            return
        screenshot(img, display)
        if not os.path.exists(img):
            say(f"  ! screenshot failed (Screen Recording permission?)")
            return
        after = front()
        if after and (after["pid"], after["win_id"]) != (f["pid"], f["win_id"]):
            # you switched while we were capturing: the picture and the app/URL we
            # read no longer match. Throw it away and capture the new window instead.
            os.remove(img)
            self.trigger("app_switch" if after["pid"] != f["pid"] else "window_change")
            return
        meta = {
            "ts": ts, "iso": datetime.now().isoformat(timespec="seconds"),
            "app": f["app"], "bundle_id": f["bundle_id"], "window": f["window"],
            "url": url, "site": site, "tab_title": tab_title,
            "screen": {"w": int(size.width), "h": int(size.height)}, "display": display,
            "image": ts + ".jpg", "bytes": os.path.getsize(img),
            "trigger": trigger, "pinned": pinned, "session": self.session,
            "inputs": inputs, "pointer": pointer,
        }
        meta_path = os.path.join(DATA_DIR, ts + ".json")
        self.last_ts = ts
        with open(meta_path, "w") as fh:
            json.dump(meta, fh, indent=2)
        self.stats["captured"] += 1
        self.q.put((meta_path, meta, trigger, pinned))

    # -- resolver thread

    # -- dictated notes

    def open_note(self):
        """Hotkey pressed: open the note window for whatever is in front RIGHT NOW,
        in any app. If memory hasn't caught up with it yet (you just switched),
        take a screenshot first; the note is attached once that's resolved."""
        f = front() or {}
        with self.lock:
            cur = self.events[-1] if self.events else None
            item = self.items.get(cur["item"]) if cur else None
            known = cur is not None and cur.get("_raw") == (f.get("app"), f.get("window"))
        if known:
            label, target = item["doing"], ("item", item["id"])
        else:
            n = self.stats["captured"]
            self.capture("note", pinned=True)
            ts = self.last_ts if self.stats["captured"] > n else None
            label = f"{f.get('app', 'this screen')}" + (f": {f['window']}" if f.get("window") else "")
            target = ("frame", ts) if ts else ("item", item["id"] if item else None)
        self.panel.show(label, lambda text: self.save_note(target, text))

    def save_note(self, target, text):
        if not text:
            line(datetime.now().strftime("%H:%M:%S"), "", "note cancelled")
            return
        at = datetime.now().isoformat(timespec="seconds")
        kind, key = target
        if kind == "frame":
            # wait (briefly) for the resolver to turn that screenshot into a memory entry
            deadline = time.time() + 30
            while key not in self.frame_item and time.time() < deadline:
                time.sleep(0.2)
            item_id = self.frame_item.get(key)
        else:
            item_id = key
        with self.lock:
            item = self.items.get(item_id)
            note = {"at": at, "text": text}
            if item:
                note["while"] = item["doing"]
                item.setdefault("notes", []).append(note)
                item["last_seen"] = at
            self.notes.append({"item": item_id, **note})
            self.save()
        line(at[11:19], (item or {}).get("app", "?"), f'note: "{text[:90]}"')

    def worker(self):
        while True:
            item = self.q.get()
            if item is None:
                return
            meta_path, meta, trigger, pinned = item
            try:
                with objc.autorelease_pool(), self.lock:
                    self.handle(meta_path, meta, trigger, pinned)
            except Exception as e:
                say(f"  ! {meta['ts']}: {e}")
            finally:
                self.q.task_done()

    def handle(self, meta_path, meta, trigger, pinned):
        now = time.mktime(time.strptime(meta["ts"], "%Y%m%d-%H%M%S"))
        img = activity.load(os.path.join(DATA_DIR, meta["image"]))
        last = self.last_frame
        sig = (meta.get("app"), meta.get("window"), meta.get("url"))

        # 1. pixels first: an unchanged screen of the same window needs no OCR at all
        same_window = last is not None and last["sig"] == sig
        change = activity.diff(last["img"], img) if same_window else None
        if change is not None and not change["regions"] and not pinned:
            res, st = last["res"], last["st"]
            self.stats["no_ocr"] += 1
        else:
            res = resolver.resolve(meta_path)
            st = understand.describe(res, meta)

        # 2. which thing is this?
        cur = self.events[-1] if self.events else None
        scrolled = bool(change and change["scroll"]) or (meta.get("inputs") or {}).get("scroll", 1e9) < 3 * self.every
        item_id, ref = self.item_for(st, cur, res, trigger, scrolled)
        item = self.items.get(item_id)
        same_thing = last is not None and last["item"] == item_id
        if not same_thing:
            change = None                  # diffing two different things means nothing
        elif change is None:
            change = activity.diff(last["img"], img)    # same thing, its URL/title changed

        # 3. what happened since the last frame of it: typing / reading / receiving / focus
        dt = min(now - last["t"], 3 * self.every) if same_thing else 0
        scale = res["image_size"]["w"] / meta["screen"]["w"] if meta.get("screen") else 1
        ptr = meta.get("pointer")
        act = activity.classify(change, last["res"] if same_thing else None, res,
                                meta.get("inputs") or {"key": 1e9, "scroll": 1e9, "click": 1e9},
                                (ptr["x"] * scale, ptr["y"] * scale) if ptr else None, dt,
                                kind=st["kind"])
        self.last_frame = {"sig": sig, "img": img, "res": res, "st": st, "item": item_id, "t": now}
        if act["category"] == "typing":
            st = dict(st, doing=st.get("doing_typing") or st["doing"])

        # 4. the memory: one entry per thing
        state_hash = hashlib.sha1(json.dumps(st["details"], sort_keys=True).encode()).hexdigest()[:12]
        frame_used = False
        if item is None:
            item = self.items[item_id] = {
                "id": item_id, "app": st["app"], "kind": st["kind"], "title": st["title"],
                "doing": st["doing"], "mostly": None, "state": st["details"],
                "activity": {c: {"seconds": 0, "text": []} for c in CATEGORIES},
                "first_seen": meta["iso"], "last_seen": meta["iso"],
                "seconds": 0, "visits": 0, "updates": 0,
                "screenshot": meta["image"], "content_hash": state_hash, "ref": ref, "refs": [ref]}
            frame_used = True
            self.stats["new_items"] += 1
        else:
            item["last_seen"] = meta["iso"]
            item["doing"] = st["doing"]
            if state_hash != item["content_hash"] or pinned:
                # same thing, new content (the draft grew, the doc changed): update it in
                # place and swap its one screenshot for the newer one
                item.update(state=st["details"] or item["state"], title=st["title"] or item["title"],
                            content_hash=state_hash)
                item["updates"] += 1
                self.drop_frame(item["screenshot"])
                item["screenshot"] = meta["image"]
                frame_used = True
        if pinned:
            item["pinned"] = True
        self.record(item["activity"], act, dt)
        if act["category"] == "typing":
            boxes = [o["box"] for o in res["objects"] if o["text"] in act["new_text"]]
            if item.get("typing_area"):
                boxes.append(item["typing_area"])
            if boxes:
                x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
                x1 = max(b[0] + b[2] for b in boxes); y1 = max(b[1] + b[3] for b in boxes)
                item["typing_area"] = [x0, y0, x1 - x0, y1 - y0]
        item["mostly"] = mostly(item["activity"])
        if not item["title"] and authored(item):
            item["title"] = item["activity"]["typing"]["text"][0][:60]   # untitled: name it by what you wrote

        # 5. the timeline: when you were on which item, and what you were doing there
        t = hms(meta["ts"])
        if cur and cur["item"] == item_id:
            self.extend(cur, now, t)
            cur["doing"] = st["doing"]
        else:
            if cur:
                # the gap between its last frame and now: you kept doing what you were doing
                gap = int(now - (last["t"] if last else now))
                cat = cur.get("_last_cat") or "reading"
                if gap > 0 and cur["item"] in self.items:
                    cur["activity"][cat] = cur["activity"].get(cat, 0) + gap
                    cur["mostly"] = max(cur["activity"], key=cur["activity"].get)
                    prev_item = self.items[cur["item"]]
                    prev_item["activity"][cat]["seconds"] += gap
                    prev_item["mostly"] = mostly(prev_item["activity"])
                self.extend(cur, now, t)
            item["visits"] += 1
            cur = {"from": t, "to": t, "seconds": 0, "item": item_id, "app": st["app"],
                   "doing": st["doing"], "activity": {}, "trigger": trigger, "_start": now}
            cur["_raw"] = (meta.get("app"), meta.get("window"))
            self.events.append(cur)
            back = item["visits"] > 1
            line(t, st["app"], st["doing"] + ("  (back to it)" if back else ""))
        if dt:
            cur["activity"][act["category"]] = cur["activity"].get(act["category"], 0) + int(dt)
            cur["mostly"] = max(cur["activity"], key=cur["activity"].get)
        cur["_last_cat"] = act["category"]
        if act["new_text"] and act["category"] in ("typing", "receiving"):
            line(t, "", f"  {act['category']}: {act['new_text'][0][:80]}")

        self.frame_item[meta["ts"]] = item_id
        cur["_raw"] = (meta.get("app"), meta.get("window"))
        if not frame_used:
            self.drop_frame(meta["image"])
            self.stats["no_change"] += 1
        self.save()

    @staticmethod
    def record(acts, act, dt):
        """Add this moment to the thing's activity: seconds, and the text involved."""
        a = acts[act["category"]]
        a["seconds"] += int(dt)
        if act["category"] == "receiving" and act["new_text"]:
            a["count"] = a.get("count", 0) + 1
        texts = act["new_text"] + ([act["pointer_on"]] if act.get("pointer_on") and
                                   act["category"] == "focus" else [])
        for txt in texts:
            if txt in a["text"]:
                a["text"].remove(txt)
            a["text"].append(txt)
        del a["text"][:-KEEP_TEXT]                    # newest KEEP_TEXT lines

    def item_for(self, st, cur, res, trigger, scrolled):
        """
        Which memory item this screen belongs to -> (item id, ref). Same rule for every app.

        The ref (understand.py) names WHERE you are: a URL, a window, a draft slot.
        What you TYPED there tells instances apart:
          - same place, and your earlier text is still on screen      -> the same thing
          - same place, your text vanished while you stayed on it (no scroll), or you
            come back and the spot you typed into is empty          -> a NEW thing that
            just looks the same (a second email, a new note, a fresh prompt)
          - conversations (it has received text from others) never split
          - new place reached without navigating (no app/tab switch), while what you
            typed is still on screen, or the old place only had a placeholder name
            ("new", "untitled")                                      -> the same thing,
            whose URL/id/title changed (a draft got saved, a doc got a name)
          - anything else is a different thing: two chats in one WhatsApp tab are two
        """
        ref = understand.ref(st)
        on_screen = [o["text"] for o in res["objects"]
                     if o["text"] and o["kind"] not in understand.CHROME]
        cur_item = self.items.get(cur["item"]) if cur else None

        instances = [i for i in self.items.values() if ref in i.get("refs", [i.get("ref")])]
        if instances:
            # back on a place we know: which instance is on screen?
            for inst in sorted(instances, key=lambda i: i["last_seen"], reverse=True):
                if authored(inst) and still_there(inst, on_screen):
                    return inst["id"], ref
            latest = max(instances, key=lambda i: i["last_seen"])
            if (authored(latest) and not scrolled and not conversation(latest)
                    and (trigger == "timer" or is_empty_where_typed(latest, res))):
                n = len(instances) + 1           # your text is gone: a fresh one, same place
                iid = make_id(st, f"{ref}#{n}")
                return iid, ref
            return latest["id"], ref

        if (cur_item and trigger == "timer" and cur_item["app"] == st["app"]
                and cur_item["kind"] == st["kind"]
                and (still_there(cur_item, on_screen)
                     or (provisional(cur_item) and not authored(cur_item)))):
            # you didn't go anywhere, but the place's name changed: same thing, new ref
            cur_item.setdefault("refs", [cur_item["ref"]]).append(ref)
            cur_item["ref"] = ref
            return cur_item["id"], ref
        return make_id(st, ref), ref

    def extend(self, ev, now, t):
        secs = int(now - ev["_start"])
        self.items[ev["item"]]["seconds"] += secs - ev["seconds"]
        ev["seconds"], ev["to"] = secs, t

    def drop_frame(self, image):
        for p in (os.path.join(DATA_DIR, image), os.path.join(DATA_DIR, image[:-4] + ".json")):
            try:
                os.remove(p)
            except OSError:
                pass

    def save(self):
        items = sorted(self.items.values(), key=lambda i: i["last_seen"], reverse=True)
        # the bookkeeping (refs, hashes, typing area) lives in its own file;
        # memory.json is only what's worth reading
        write_json(INTERNAL_FILE, {"items": items})
        write_json(ITEMS_FILE, {"updated": nice_time(datetime.now().isoformat(timespec="seconds")),
                                "things": [readable(i) for i in items]})
        by_app = Counter()
        for e in self.events:
            by_app[e["app"]] += e["seconds"]
        write_json(os.path.join(SESSIONS_DIR, self.session + ".json"), {
            "session": self.session,
            "time_by_app": {a: duration(s) for a, s in by_app.most_common()},
            "timeline": [{"from": e["from"], "to": e["to"], "for": duration(e["seconds"]),
                          "app": e["app"], "doing": e["doing"],
                          **({"mostly": e["mostly"]} if e.get("mostly") else {}),
                          "memory": e["item"]} for e in self.events],
            **({"notes": [{"at": nice_time(n["at"]), "on": n["item"], "text": n["text"]}
                          for n in self.notes]} if self.notes else {}),
        })

    # -- lifecycle

    def run(self):
        c = cg()
        if not c["CGPreflightScreenCaptureAccess"]():
            c["CGRequestScreenCaptureAccess"]()
            sys.exit("Screen Recording permission is not granted to this terminal.\n"
                     "System Settings -> Privacy & Security -> Screen Recording, enable it,\n"
                     "quit and reopen the terminal, then run again.")
        os.makedirs(MEMORY_DIR, exist_ok=True)
        with open(PIDFILE, "w") as fh:
            fh.write(str(os.getpid()))

        def stop(*_):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGUSR1, lambda *_: setattr(self, "pin", True))
        signal.signal(signal.SIGUSR2, lambda *_: setattr(self, "note_request", True))
        app = dictation.start_app()
        hotkey_ok = dictation.register_hotkey(lambda: setattr(self, "note_request", True))
        dictation.ensure_listener()        # build the speech helper now, not on first ⌃⌥N

        events = Events.alloc().initWithTracker_(self)
        subscribe(events)
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()

        quiet_system_logs()
        say(f"LMemM is watching  ·  captures on app/tab switches, else every {self.every}s"
            f"  ·  pauses after {IDLE}s idle")
        self.last_sig = front()
        self.last_capture = time.time()      # the "start" trigger takes the first frame
        self.trigger("start")

        say((f"{dictation.HOTKEY_LABEL} dictate a note" if hotkey_ok
             else f"(couldn't register {dictation.HOTKEY_LABEL}: use  python3 lmemm.py note)")
            + "  ·  Ctrl-C stop\n")
        try:
            while True:
                # deliver events (hotkey, note window) and notifications, waiting up to 0.25s
                ev = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                    0xFFFFFFFFFFFFFFFF, Foundation.NSDate.dateWithTimeIntervalSinceNow_(0.25),
                    Foundation.NSDefaultRunLoopMode, True)
                if ev is not None:
                    app.sendEvent_(ev)
                self.tick()
        except KeyboardInterrupt:
            pass
        finally:
            self.finish()

    def finish(self):
        say("\nstopping…")
        self.q.put(None)
        self.thread.join(timeout=60)
        try:
            if open(PIDFILE).read().strip() == str(os.getpid()):
                os.remove(PIDFILE)
        except OSError:
            pass
        s = self.stats
        spent, visits = Counter(), Counter()
        for e in self.events:                       # this session only
            spent[e["item"]] += e["seconds"]
            visits[e["item"]] += 1
        notes = Counter(n["item"] for n in self.notes)
        first = self.events[0]["from"] if self.events else "-"
        last = self.events[-1]["to"] if self.events else "-"
        say(f"\nsession {first} → {last}  ·  {s['captured']} screenshots → {len(spent)} thing{'s' * (len(spent) != 1)}"
            + (f"  ·  {len(self.notes)} note{'s' * (len(self.notes) != 1)}" if self.notes else "")
            + (f"  ·  {s['skipped']} skipped (sensitive)" if s["skipped"] else "") + "\n")
        for iid, secs in spent.most_common():
            i = self.items[iid]
            extra = [f"{visits[iid]} visits" if visits[iid] > 1 else "",
                     i.get("mostly") or "",
                     f"{notes[iid]} note{'s' * (notes[iid] != 1)}" if notes[iid] else ""]
            extra = "  ·  ".join(x for x in extra if x)
            say(f"  {duration(secs):>7}  {i['app'][:14]:14}  {i['doing'][:70]}"
                + (f"   ({extra})" if extra else ""))
        say(f"\nsaved to {os.path.relpath(ITEMS_FILE)}")


ITEMS_FILE = os.path.join(MEMORY_DIR, "memory.json")
INTERNAL_FILE = os.path.join(MEMORY_DIR, ".index.json")
CATEGORIES = ("typing", "reading", "receiving", "focus")
KEEP_TEXT = 15


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
    """Anything that has received text from others is a stream (a chat, a thread):
    your messages scrolling out of view doesn't make it a new one."""
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


def mostly(acts):
    secs = {c: a["seconds"] for c, a in acts.items() if a["seconds"]}
    return max(secs, key=secs.get) if secs else None
SESSIONS_DIR = os.path.join(MEMORY_DIR, "sessions")


def load_items():
    try:
        src = INTERNAL_FILE if os.path.exists(INTERNAL_FILE) else ITEMS_FILE   # older runs: memory.json
        with open(src) as fh:
            items = {i["id"]: i for i in json.load(fh)["items"]}
        for i in items.values():          # entries written before activity tracking existed
            i.setdefault("activity", {c: {"seconds": 0, "text": []} for c in CATEGORIES})
            i.setdefault("mostly", None)
        return items
    except (OSError, ValueError, KeyError):
        return {}


def nice_time(iso):
    return iso.replace("T", " ")[:16] if iso else None


def duration(s):
    s = int(s or 0)
    return f"{s // 3600}h {s % 3600 // 60}m" if s >= 3600 else f"{s // 60}m {s % 60}s" if s >= 60 else f"{s}s"


def readable(i):
    """One memory entry as a person would want to read it: what, what you did, your notes."""
    acts = {}
    for c, a in i.get("activity", {}).items():
        if not a["seconds"] and not a["text"]:
            continue
        entry = {"time": duration(a["seconds"])}
        if a.get("count"):
            entry["times"] = a["count"]
        if a["text"]:
            entry["text"] = a["text"][-8:]
        acts[c] = entry
    out = {
        "id": i["id"],
        "app": i["app"],
        "what": i.get("title") or i["doing"],
        "doing": i["doing"],
    }
    if i.get("notes"):
        out["your_notes"] = [{"at": nice_time(n["at"]), "text": n["text"]} for n in i["notes"]]
    latest = {k: v for k, v in (i.get("state") or {}).items() if v != out["what"]}
    if latest:                                   # e.g. an email's to / subject / draft
        out["latest"] = latest
    if acts:
        out["mostly"] = i.get("mostly")
        out["activity"] = acts
    out["time"] = {"total": duration(i["seconds"]), "visits": i["visits"],
                   "first": nice_time(i["first_seen"]), "last": nice_time(i["last_seen"])}
    out["screenshot"] = i["screenshot"]
    if i.get("pinned"):
        out["pinned"] = True
    return out


def write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    os.replace(path + ".tmp", path)


def note():
    try:
        pid = int(open(PIDFILE).read().strip())
        os.kill(pid, signal.SIGUSR2)
        print("note window opened.")
    except (OSError, ValueError):
        sys.exit("LMemM isn't running.")


def pin():
    try:
        pid = int(open(PIDFILE).read().strip())
        os.kill(pid, signal.SIGUSR1)
        print("pinned the current screen.")
    except (OSError, ValueError):
        sys.exit("LMemM isn't running.")


if __name__ == "__main__":
    Tracker().run()
