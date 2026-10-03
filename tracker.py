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
from datetime import datetime

try:
    import objc
    import Foundation
    from AppKit import NSObject, NSScreen, NSWorkspace
except ImportError:
    sys.exit("Missing dependency. Run:  pip3 install pyobjc-framework-Cocoa")

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


def idle_seconds():
    # HID system state, any input event type
    return cg()["CGEventSourceSecondsSinceLastEventType"](1, 0xFFFFFFFF)


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
        return 1, screens[0].frame().size
    main_h = screens[0].frame().size.height
    cx = bounds["X"] + bounds["Width"] / 2
    cy = main_h - (bounds["Y"] + bounds["Height"] / 2)      # CG top-left -> Cocoa bottom-left
    for i, s in enumerate(screens):
        f = s.frame()
        if f.origin.x <= cx < f.origin.x + f.size.width and f.origin.y <= cy < f.origin.y + f.size.height:
            return i + 1, f.size
    return 1, screens[0].frame().size


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
                say(f"          paused: {reason}")
                self.paused = reason
            self.pending = None
            return
        if self.paused:
            say(f"          resumed")
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
            say(f"{datetime.now():%H:%M:%S}  {trigger:13}  {f['app'][:22]:22}  SKIP  {skip}")
            return

        display, size = display_for(f["bounds"])
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
        }
        meta_path = os.path.join(DATA_DIR, ts + ".json")
        with open(meta_path, "w") as fh:
            json.dump(meta, fh, indent=2)
        self.stats["captured"] += 1
        self.q.put((meta_path, meta, trigger, pinned))

    # -- resolver thread

    def worker(self):
        while True:
            item = self.q.get()
            if item is None:
                return
            meta_path, meta, trigger, pinned = item
            try:
                with objc.autorelease_pool():
                    self.handle(meta_path, meta, trigger, pinned)
            except Exception as e:
                say(f"  ! {meta['ts']}: {e}")
            finally:
                self.q.task_done()

    def handle(self, meta_path, meta, trigger, pinned):
        res = resolver.resolve(meta_path)
        st = understand.describe(res, meta)
        now = time.mktime(time.strptime(meta["ts"], "%Y%m%d-%H%M%S"))
        cur = self.events[-1] if self.events else None
        item_id = self.item_for(st, cur)
        item = self.items.get(item_id)
        frame_used = False

        # -- the memory: one entry per thing
        state_hash = hashlib.sha1(json.dumps(st["details"], sort_keys=True).encode()).hexdigest()[:12]
        if item is None:
            item = self.items[item_id] = {
                "id": item_id, "app": st["app"], "kind": st["kind"], "title": st["title"],
                "doing": st["doing"], "state": st["details"],
                "first_seen": meta["iso"], "last_seen": meta["iso"],
                "seconds": 0, "visits": 0, "updates": 0,
                "screenshot": meta["image"], "content_hash": state_hash, "ref": understand.ref(st)}
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

        # -- the timeline: when you were on which item
        t = hms(meta["ts"])
        if cur and cur["item"] == item_id:
            self.extend(cur, now, t)
            cur["doing"] = st["doing"]
        else:
            if cur:
                self.extend(cur, now, t)
            item["visits"] += 1
            self.events.append({"from": t, "to": t, "seconds": 0, "item": item_id,
                                "app": st["app"], "doing": st["doing"], "trigger": trigger,
                                "_start": now})
            back = item["visits"] > 1
            say(f"{t}  {trigger:13}  {st['app'][:16]:16}  {st['doing']}"
                + ("   (back to it)" if back else ""))
        if not frame_used:
            self.drop_frame(meta["image"])
            self.stats["no_change"] += 1
        self.save()

    def item_for(self, st, cur):
        """Which memory item this screen belongs to."""
        ref = understand.ref(st)
        iid = f'{st["kind"]}-{hashlib.sha1(ref.encode()).hexdigest()[:8]}'
        cur_item = self.items.get(cur["item"]) if cur else None
        if st["kind"] == "email_draft" and cur_item and cur_item["kind"] == "email_draft":
            if ref.endswith("draft:new"):
                return cur["item"]               # Gmail hasn't assigned the draft an id yet
            if cur_item["ref"].endswith("draft:new") and iid not in self.items:
                # ...and now it has: the "new" draft we were tracking is this one
                self.items[iid] = self.items.pop(cur["item"])
                self.items[iid].update(id=iid, ref=ref)
                for e in self.events:
                    if e["item"] == cur["item"]:
                        e["item"] = iid
        return iid

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
        strip = lambda d: {k: v for k, v in d.items() if not k.startswith("_")}
        write_json(ITEMS_FILE, {"items": sorted(self.items.values(), key=lambda i: i["last_seen"],
                                                reverse=True)})
        by_app = Counter()
        for e in self.events:
            by_app[e["app"]] += e["seconds"]
        write_json(os.path.join(SESSIONS_DIR, self.session + ".json"), {
            "session": self.session,
            "timeline": [strip(e) for e in self.events],
            "seconds_by_app": dict(by_app.most_common()),
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

        events = Events.alloc().initWithTracker_(self)
        subscribe(events)
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()

        say(f"LMemM session {self.session}  -> {MEMORY_DIR}")
        say(f"captures on app/tab/window change, else every {self.every}s; pauses after {IDLE}s idle.")
        say("Ctrl-C to stop.  python3 lmemm.py pin  pins the current screen.\n")
        self.last_sig = front()
        self.last_capture = time.time()      # the "start" trigger takes the first frame
        self.trigger("start")

        loop = Foundation.NSRunLoop.currentRunLoop()
        try:
            while True:
                # deliver pending notifications, then wait up to 0.25s for more
                loop.runMode_beforeDate_(Foundation.NSDefaultRunLoopMode,
                                         Foundation.NSDate.dateWithTimeIntervalSinceNow_(0.25))
                self.tick()
        except KeyboardInterrupt:
            pass
        finally:
            self.finish()

    def finish(self):
        say("\nstopping: resolving what's still queued ...")
        self.q.put(None)
        self.thread.join(timeout=60)
        try:
            if open(PIDFILE).read().strip() == str(os.getpid()):
                os.remove(PIDFILE)
        except OSError:
            pass
        s = self.stats
        touched = {e["item"] for e in self.events}
        say(f"\nsession {self.session}")
        say(f"  {s['captured']} screenshots -> {len(touched)} things ({s['new_items']} new),"
            f" {len(self.events)} stretches of time; {s['no_change']} screenshots showed nothing new"
            f" and were deleted; {s['skipped']} sensitive skipped\n")
        for i in sorted((self.items[t] for t in touched), key=lambda i: -i["seconds"]):
            say(f"  {i['seconds']:5d}s  x{i['visits']}  {i['app'][:14]:14}  {i['doing']}")
        say(f"\nmemory:   {ITEMS_FILE}\ntimeline: {os.path.join(SESSIONS_DIR, self.session + '.json')}")


ITEMS_FILE = os.path.join(MEMORY_DIR, "memory.json")
SESSIONS_DIR = os.path.join(MEMORY_DIR, "sessions")


def load_items():
    try:
        with open(ITEMS_FILE) as fh:
            return {i["id"]: i for i in json.load(fh)["items"]}
    except (OSError, ValueError, KeyError):
        return {}


def write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    os.replace(path + ".tmp", path)


def pin():
    try:
        pid = int(open(PIDFILE).read().strip())
        os.kill(pid, signal.SIGUSR1)
        print("pinned the current screen.")
    except (OSError, ValueError):
        sys.exit("LMemM isn't running.")


if __name__ == "__main__":
    Tracker().run()
