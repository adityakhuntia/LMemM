"""LMemM - everything that talks to macOS: the front window, browser tab, displays,
screenshots, input counters, pointer, workspace notifications.

All cheap: the front window is one CGWindowList call (~0.2 ms); browser URLs come
from in-process AppleScript compiled once; idle/input counters are system counters
(seconds since the last key / scroll / click, never which key).
"""

import os
import subprocess
import sys

try:
    import objc
    import Foundation
    from AppKit import NSEvent, NSObject, NSScreen, NSWorkspace
except ImportError:
    sys.exit("Missing dependency. Run:  python3 -m pip install -r requirements.txt")

import config

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


def screen_recording_allowed(request=True):
    c = cg()
    if c["CGPreflightScreenCaptureAccess"]():
        return True
    if request:
        c["CGRequestScreenCaptureAccess"]()
    return False


def idle_seconds(event_type=0xFFFFFFFF):
    """Seconds since the last input event (HID system state); default = any type."""
    return cg()["CGEventSourceSecondsSinceLastEventType"](1, event_type)


def input_ages():
    """Seconds since the last key press, scroll, and click. Counters only."""
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
    for w in cg()["CGWindowListCopyWindowInfo"](1 | 16, 0) or []:   # on-screen, front to back
        if w.get("kCGWindowOwnerPID") != pid or w.get("kCGWindowLayer") != 0:
            continue
        b = w.get("kCGWindowBounds") or {}
        if b.get("Height", 0) < 80 or b.get("Width", 0) < 80:
            continue
        win = w
        break
    return {
        "app": app.localizedName(),
        "bundle_id": app.bundleIdentifier(),
        "pid": pid,
        "win_id": win.get("kCGWindowNumber") if win else None,
        "window": (win.get("kCGWindowName") or None) if win else None,
        "bounds": dict(win.get("kCGWindowBounds")) if win else None,
    }


_SCRIPTS = {}


def browser_info(app):
    """(URL, tab title, private?) of the front tab, or (None, None, False)."""
    if app not in config.BROWSERS:
        return None, None, False
    if app not in _SCRIPTS:
        if app == "Safari":
            src = 'tell application "Safari" to get {URL, name} of front document'
        else:
            src = (f'tell application "{app}" to get {{URL, title}} of active tab of front window'
                   f' & {{mode of front window}}')
        _SCRIPTS[app] = Foundation.NSAppleScript.alloc().initWithSource_(src)
    res, _err = _SCRIPTS[app].executeAndReturnError_(None)
    if res is None:
        return None, None, False
    vals = [res.descriptorAtIndex_(i).stringValue() for i in range(1, res.numberOfItems() + 1)]
    url, title = vals[0], vals[1] if len(vals) > 1 else None
    private = len(vals) > 2 and vals[2] == "incognito"
    return url, title, private


def display_for(bounds):
    """(1-based `screencapture -D` index, NSScreen frame) of the display holding the window."""
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


def display_bounds(display):
    """A display's frame in CG (top-left origin) coordinates, like window bounds."""
    screens = NSScreen.screens()
    frame = screens[display - 1].frame()
    return {"X": frame.origin.x,
            "Y": screens[0].frame().size.height - frame.origin.y - frame.size.height,
            "Width": frame.size.width, "Height": frame.size.height}


def screenshot(path, display):
    subprocess.run(["screencapture", "-x", "-o", "-t", "jpg", "-D", str(display), path],
                   check=False)
    if os.path.exists(path):
        subprocess.run(["sips", "-Z", str(config.SCALE_PX), path], capture_output=True, check=False)


def notify(title, message):
    """A macOS notification banner. Fire and forget; never blocks the tracker."""
    esc = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')
    try:
        subprocess.Popen(["osascript", "-e",
                          f'display notification "{esc(message)}" with title "{esc(title)}"'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


# ---------------------------------------------------------------- system events

class Events(NSObject):
    """Receives NSWorkspace / distributed notifications on the main run loop and
    forwards them to a handler with .trigger(why) and .set_flag(name, on)."""

    def initWithHandler_(self, handler):
        self = objc.super(Events, self).init()
        self.handler = handler
        return self

    def appSwitched_(self, note):
        self.handler.trigger("app_switch")

    def willSleep_(self, note):
        self.handler.set_flag("asleep", True)

    def didWake_(self, note):
        self.handler.set_flag("asleep", False)

    def screensSlept_(self, note):
        self.handler.set_flag("display_off", True)

    def screensWoke_(self, note):
        self.handler.set_flag("display_off", False)

    def locked_(self, note):
        self.handler.set_flag("locked", True)

    def unlocked_(self, note):
        self.handler.set_flag("locked", False)


def subscribe(handler):
    events = Events.alloc().initWithHandler_(handler)
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
    return events


def next_event(app, timeout=0.25):
    """Deliver one pending AppKit event (hotkey, note window) and run-loop notifications."""
    ev = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
        0xFFFFFFFFFFFFFFFF, Foundation.NSDate.dateWithTimeIntervalSinceNow_(timeout),
        Foundation.NSDefaultRunLoopMode, True)
    if ev is not None:
        app.sendEvent_(ev)


def quiet_system_logs():
    """macOS input-method frameworks NSLog noise straight to the terminal whenever a text
    box gets focus. Send the raw stderr fd to /dev/null; keep Python's errors visible."""
    try:
        real = os.dup(2)
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
        sys.stderr = os.fdopen(real, "w", buffering=1)
    except OSError:
        pass
