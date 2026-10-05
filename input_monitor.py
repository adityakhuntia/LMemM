"""Opt-in listen-only adapter. No key values or accessibility text values are read."""

import ctypes
import hashlib
import time

SUPPORTED_INPUT_APPS = {"com.microsoft.VSCode"}


def secure_input_enabled():
    try:
        carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
        fn = carbon.IsSecureEventInputEnabled
        fn.restype = ctypes.c_bool
        return bool(fn())
    except (OSError, AttributeError):
        return None


def context_id(f):
    # Session-local association, not a durable document ID. Titles are not retained.
    raw = repr((f.get("pid"), f.get("win_id"), f.get("window"))).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def permitted_context(allowed_apps):
    if secure_input_enabled() is not False:
        return None
    try:
        import Quartz as q
        import tracker
        if not q.AXIsProcessTrusted():
            return None
        f = tracker.front()
        if not f or f.get("bundle_id") not in allowed_apps or not f.get("bounds") or not f.get("win_id"):
            return None
        if tracker.SKIP_TITLES.search(f.get("window") or ""):
            return None
        system = q.AXUIElementCreateSystemWide()
        err, element = q.AXUIElementCopyAttributeValue(system, "AXFocusedUIElement", None)
        if err or element is None:
            return None
        err, role = q.AXUIElementCopyAttributeValue(element, "AXRole", None)
        if err or role not in {"AXTextArea", "AXTextField", "AXOutline", "AXButton", "AXGroup", "AXScrollArea"}:
            return None
        sub_err, subrole = q.AXUIElementCopyAttributeValue(element, "AXSubrole", None)
        if subrole == "AXSecureTextField" or role == "AXTextField" and (sub_err or subrole is None):
            return None
        after = tracker.front()
        if after is None or any(after.get(k) != f.get(k) for k in ("pid", "win_id", "window", "bounds")):
            return None
        return {"id": context_id(f), "bundle_id": f["bundle_id"], "window_id": f["win_id"], "bounds": f["bounds"]}
    except Exception:
        return None


def native_uptime_ns():
    lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
    class Timebase(ctypes.Structure):
        _fields_ = [("numer", ctypes.c_uint32), ("denom", ctypes.c_uint32)]
    lib.mach_absolute_time.restype = ctypes.c_uint64
    info = Timebase()
    lib.mach_timebase_info(ctypes.byref(info))
    return lib.mach_absolute_time() * info.numer // info.denom


class InputMonitor:
    def __init__(self, aggregator, allowed_apps, context_provider=permitted_context, on_gap=None,
                 native=None, clock=time.monotonic_ns, native_clock=native_uptime_ns):
        if not allowed_apps or not allowed_apps <= SUPPORTED_INPUT_APPS:
            raise ValueError("initial input monitoring supports only com.microsoft.VSCode")
        if native is None:
            import Quartz
            native = Quartz
        self.native = native
        self.aggregator = aggregator
        self.allowed_apps = allowed_apps
        self.context_provider = context_provider
        self.on_gap = on_gap or (lambda reason: None)
        self.clock, self.native_clock = clock, native_clock
        self.tap = self.source = self.loop = None
        self.state = "off"
        self.paused = False
        self.offset_ns = 0
        self.gate = None

    def _gap(self, reason):
        if self.gate != reason:
            self.aggregator.last_ns = max(self.aggregator.last_ns, self.clock())
            self.aggregator.clear(reason)
            self.on_gap(reason)
        self.gate = reason

    def start(self, request_permission=False):
        q = self.native
        if self.tap is not None:
            return self.state == "recording"
        if not q.CGPreflightListenEventAccess():
            if request_permission:
                q.CGRequestListenEventAccess()
            self.state = "unavailable"
            self._gap("input_permission")
            return False
        if not q.AXIsProcessTrusted():
            self.state = "unavailable"
            self._gap("accessibility_permission")
            return False
        types = (q.kCGEventKeyDown, q.kCGEventMouseMoved, q.kCGEventLeftMouseDown,
                 q.kCGEventRightMouseDown, q.kCGEventOtherMouseDown, q.kCGEventLeftMouseDragged,
                 q.kCGEventRightMouseDragged, q.kCGEventOtherMouseDragged, q.kCGEventScrollWheel)
        self.offset_ns = self.clock() - self.native_clock()
        self.tap = q.CGEventTapCreate(q.kCGSessionEventTap, q.kCGHeadInsertEventTap,
                                    q.kCGEventTapOptionListenOnly, sum(1 << t for t in types),
                                    self.callback, None)
        if self.tap is None:
            self.state = "unavailable"
            self._gap("listener_unavailable")
            return False
        self.source = q.CFMachPortCreateRunLoopSource(None, self.tap, 0)
        self.loop = q.CFRunLoopGetMain()
        q.CFRunLoopAddSource(self.loop, self.source, q.kCFRunLoopCommonModes)
        q.CGEventTapEnable(self.tap, True)
        self.state = "recording"
        return True

    def set_paused(self, paused):
        if paused and not self.paused:
            self._gap("paused")
        self.paused = paused

    def stop(self):
        q = self.native
        self._gap("stopped")
        if self.tap is not None:
            q.CGEventTapEnable(self.tap, False)
            q.CFRunLoopRemoveSource(self.loop, self.source, q.kCFRunLoopCommonModes)
            q.CFMachPortInvalidate(self.tap)
        self.tap = self.source = self.loop = None
        self.state = "off"

    def status(self):
        return {"state": "paused" if self.paused and self.state == "recording" else self.state,
                "gap": self.gate, "allowed_apps": sorted(self.allowed_apps)}

    def callback(self, proxy, kind, event, user_info):
        q = self.native
        try:
            if kind in (q.kCGEventTapDisabledByTimeout, q.kCGEventTapDisabledByUserInput):
                self.state = "disabled"
                self._gap("listener_disabled")
                return event
            if self.paused or self.state != "recording":
                return event
            ns = int(q.CGEventGetTimestamp(event)) + self.offset_ns
            lag = self.clock() - ns
            if lag < -10_000_000 or lag > 100_000_000:
                self._gap("delayed_event")
                return event
            context = self.context_provider(self.allowed_apps)
            if context is None or context.get("bundle_id") not in self.allowed_apps:
                self._gap("protected_or_excluded")
                return event
            if kind == q.kCGEventKeyDown:
                name, payload = "key", {}
            else:
                point = q.CGEventGetLocation(event)
                b = context["bounds"]
                x = int(3 * (point.x - b["X"]) / b["Width"])
                y = int(3 * (point.y - b["Y"]) / b["Height"])
                region = ("top", "middle", "bottom")[y] + "-" + ("left", "center", "right")[x] if 0 <= x < 3 and 0 <= y < 3 else "unknown"
                if kind == q.kCGEventScrollWheel:
                    dy = q.CGEventGetIntegerValueField(event, q.kCGScrollWheelEventDeltaAxis1)
                    dx = q.CGEventGetIntegerValueField(event, q.kCGScrollWheelEventDeltaAxis2)
                    direction = ("up" if dy > 0 else "down") if abs(dy) >= abs(dx) else ("left" if dx > 0 else "right")
                    size = max(abs(dx), abs(dy))
                    name, payload = "scroll", {"direction": direction, "magnitude": "small" if size < 10 else "medium" if size < 50 else "large"}
                elif kind in (q.kCGEventLeftMouseDown, q.kCGEventRightMouseDown, q.kCGEventOtherMouseDown):
                    name, payload = "click", {"region": region, "button": "left" if kind == q.kCGEventLeftMouseDown else "right" if kind == q.kCGEventRightMouseDown else "other"}
                else:
                    name, payload = "move" if kind == q.kCGEventMouseMoved else "drag", {"region": region}
            after = self.context_provider(self.allowed_apps)
            if after != context:
                self._gap("context_race")
                return event
            self.gate = None
            self.aggregator.feed(name, ns, context, payload)
        except Exception:
            self._gap("callback_error")
        return event
