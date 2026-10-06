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


def permitted_context(allowed_apps, on_denied=None):
    def deny(reason):
        if on_denied:
            on_denied(reason)
        return None
    secure = secure_input_enabled()
    if secure is not False:
        return deny("secure_input_unknown" if secure is None else "secure_input_active")
    try:
        import ApplicationServices as q
        import tracker
        if not q.AXIsProcessTrusted():
            return deny("accessibility_permission")
        f = tracker.front()
        if not f or f.get("bundle_id") not in allowed_apps or not f.get("bounds") or not f.get("win_id"):
            return deny("excluded_or_missing_window")
        if tracker.SKIP_TITLES.search(f.get("window") or ""):
            return deny("excluded_window")
        system = q.AXUIElementCreateSystemWide()
        err, element = q.AXUIElementCopyAttributeValue(system, "AXFocusedUIElement", None)
        if err or element is None:
            return deny("focused_element_unavailable")
        pid_err, focus_pid = q.AXUIElementGetPid(element, None)
        if pid_err or focus_pid != f["pid"]:
            return deny("focus_owner_mismatch")
        err, role = q.AXUIElementCopyAttributeValue(element, "AXRole", None)
        if err or role not in {"AXTextArea", "AXTextField", "AXOutline", "AXButton", "AXGroup", "AXScrollArea"}:
            return deny("unsupported_focus_role")
        sub_err, subrole = q.AXUIElementCopyAttributeValue(element, "AXSubrole", None)
        if subrole == "AXSecureTextField":
            return deny("secure_text_field")
        if sub_err not in (0, -25205, -25212) or role == "AXTextField" and (sub_err or subrole is None):
            return deny("unverified_focus_subrole")
        after = tracker.front()
        if after is None or any(after.get(k) != f.get(k) for k in ("pid", "win_id", "window", "bounds")):
            return deny("focus_context_changed")
        return {"id": context_id(f), "bundle_id": f["bundle_id"], "window_id": f["win_id"], "bounds": f["bounds"], "pid": f["pid"]}
    except Exception:
        return deny("focus_inspection_error")



class AccessibilitySupport:
    """Opt-in Electron structural AX support; restore only flags we changed."""
    def __init__(self, native):
        self.native = native
        self.changed = {}

    def ensure(self, foreground, allowed_apps):
        if not foreground or foreground.get("bundle_id") != "com.microsoft.VSCode" or foreground["bundle_id"] not in allowed_apps:
            return
        pid = foreground["pid"]
        if pid in self.changed:
            return
        try:
            app = self.native.AXUIElementCreateApplication(pid)
            error, enabled = self.native.AXUIElementCopyAttributeValue(app, "AXManualAccessibility", None)
            if not error and enabled is False:
                if self.native.AXUIElementSetAttributeValue(app, "AXManualAccessibility", True) == 0:
                    self.changed[pid] = app
        except Exception:
            pass  # Focus inspection still fails closed if the tree is unavailable.

    def restore(self):
        for app in self.changed.values():
            try:
                error, enabled = self.native.AXUIElementCopyAttributeValue(app, "AXManualAccessibility", None)
                if not error and enabled is True:
                    self.native.AXUIElementSetAttributeValue(app, "AXManualAccessibility", False)
            except Exception:
                pass
        self.changed.clear()


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
            import ApplicationServices
            class Bindings:
                def __getattr__(self, name):
                    return getattr(ApplicationServices if name.startswith("AX") else Quartz, name)
            native = Bindings()
        self.native = native
        self.aggregator = aggregator
        self.allowed_apps = allowed_apps
        self.context_denial = None
        if context_provider is permitted_context:
            def checked_context(apps):
                self.context_denial = None
                return permitted_context(apps, lambda reason: setattr(self, "context_denial", reason))
            self.context_provider = checked_context
        else:
            self.context_provider = context_provider
        self.accessibility_support = AccessibilitySupport(native)
        self.on_gap = on_gap or (lambda reason: None)
        self.clock, self.native_clock = clock, native_clock
        self.tap = self.source = self.loop = None
        self.accessibility_support.restore()
        self.state = "off"
        self.paused = False
        self.offset_ns = 0
        self.gate = None
        self.verified_context = None
        self.verified_since_ns = 0

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
        self.prepare_context()
        self.verify_context(self.context_provider(self.allowed_apps))
        self.tap = q.CGEventTapCreate(q.kCGAnnotatedSessionEventTap, q.kCGHeadInsertEventTap,
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

    def prepare_context(self):
        # Only the main loop calls this; no AX writes in the native callback.
        try:
            import tracker
            self.accessibility_support.ensure(tracker.front(), self.allowed_apps)
        except Exception:
            pass

    def verify_context(self, context):
        if context != self.verified_context:
            self.verified_context = context
            self.verified_since_ns = self.clock()

    def invalidate_boundary(self):
        self.verified_context = None
        self.verified_since_ns = self.clock()
        self._gap("context_boundary")

    def set_paused(self, paused):
        if paused and not self.paused:
            self._gap("paused")
            self.verify_context(None)
        self.paused = paused

    def stop(self):
        q = self.native
        self._gap("stopped")
        if self.tap is not None:
            q.CGEventTapEnable(self.tap, False)
            q.CFRunLoopRemoveSource(self.loop, self.source, q.kCFRunLoopCommonModes)
            q.CFMachPortInvalidate(self.tap)
        self.tap = self.source = self.loop = None
        self.accessibility_support.restore()
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
                self._gap(self.context_denial or "protected_or_excluded")
                self.verify_context(None)
                return event
            self.verify_context(context)
            if ns < self.verified_since_ns:
                self._gap("event_before_context")
                return event
            target_pid = q.CGEventGetIntegerValueField(event, q.kCGEventTargetUnixProcessID)
            if not context.get("pid") or target_pid != context["pid"]:
                self._gap("unknown_or_different_target")
                return event
            if kind == q.kCGEventKeyDown:
                name, payload = "key", {}
            else:
                point = q.CGEventGetLocation(event)
                b = context["bounds"]
                if not (b["X"] <= point.x < b["X"] + b["Width"] and b["Y"] <= point.y < b["Y"] + b["Height"]):
                    self._gap("pointer_outside_window")
                    return event
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
