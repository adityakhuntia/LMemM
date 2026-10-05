import unittest
from unittest.mock import patch

from input_events import Aggregator
from input_monitor import InputMonitor, permitted_context


class Native:
    kCGSessionEventTap = 1
    kCGHeadInsertEventTap = 0
    kCGEventTapOptionListenOnly = 1
    kCGEventKeyDown = 10
    kCGEventMouseMoved = 5
    kCGEventLeftMouseDown = 1
    kCGEventRightMouseDown = 3
    kCGEventOtherMouseDown = 25
    kCGEventLeftMouseDragged = 6
    kCGEventRightMouseDragged = 7
    kCGEventOtherMouseDragged = 27
    kCGEventScrollWheel = 22
    kCGEventTapDisabledByTimeout = -2
    kCGEventTapDisabledByUserInput = -1
    kCGScrollWheelEventDeltaAxis1 = 11
    kCGScrollWheelEventDeltaAxis2 = 12
    kCFRunLoopCommonModes = "common"
    def __init__(self):
        self.listen = True
        self.trusted = True
        self.tap_args = None
        self.enabled = False
    def CGPreflightListenEventAccess(self): return self.listen
    def CGRequestListenEventAccess(self): return self.listen
    def AXIsProcessTrusted(self): return self.trusted
    def CGEventTapCreate(self, *args): self.tap_args = args; return "tap"
    def CFMachPortCreateRunLoopSource(self, *args): return "source"
    def CFRunLoopGetMain(self): return "loop"
    def CFRunLoopAddSource(self, *args): pass
    def CFRunLoopRemoveSource(self, *args): pass
    def CFMachPortInvalidate(self, *args): pass
    def CGEventTapEnable(self, tap, enabled): self.enabled = enabled
    def CGEventGetTimestamp(self, event): return event["time"]
    def CGEventGetLocation(self, event): return type("Point", (), {"x": 50, "y": 50})()
    def CGEventGetIntegerValueField(self, event, field):
        if field not in (11, 12): raise AssertionError("key field read")
        return -5 if field == 11 else 0


CTX = {"id": "context", "bundle_id": "com.microsoft.VSCode", "window_id": 7,
       "bounds": {"X": 0, "Y": 0, "Width": 100, "Height": 100}}


class InputMonitorTests(unittest.TestCase):
    def setUp(self):
        self.native = Native()
        self.a = Aggregator("s", "2026-10-05T09:00:00+00:00", 0)
        self.gaps = []
        self.mon = InputMonitor(self.a, {"com.microsoft.VSCode"}, lambda apps: dict(CTX), self.gaps.append,
                                native=self.native, clock=lambda: 1_000_000_000, native_clock=lambda: 1_000_000_000)

    def test_default_adapter_registers_listen_only_and_never_reads_key_values(self):
        self.assertTrue(self.mon.start())
        self.assertEqual(self.native.tap_args[2], 1)
        event = {"time": 1_000_000_000}
        self.assertIs(self.mon.callback(None, 10, event, None), event)
        events = self.a.drain(2_000_000_000)
        self.assertEqual(events[0]["payload"], {"count": 1})
        self.mon.stop()
        self.assertFalse(self.native.enabled)

    def test_denied_permission_and_accessibility_are_unavailable(self):
        for field in ("listen", "trusted"):
            setattr(self.native, field, False)
            self.assertFalse(self.mon.start())
            self.assertIsNone(self.native.tap_args)
            setattr(self.native, field, True)

    def test_excluded_context_and_stale_event_produce_no_details(self):
        self.mon.start()
        self.mon.context_provider = lambda apps: None
        self.mon.callback(None, 10, {"time": 1_000_000_000}, None)
        self.mon.context_provider = lambda apps: dict(CTX)
        self.mon.callback(None, 10, {"time": 100_000_000}, None)
        self.assertTrue(all(e["kind"] == "gap" for e in self.a.drain(2_000_000_000)))

    def test_pausing_and_disabled_tap_clear_pending_detail(self):
        self.mon.start()
        self.mon.callback(None, 10, {"time": 1_000_000_000}, None)
        self.mon.set_paused(True)
        self.mon.callback(None, 10, {"time": 1_000_000_000}, None)
        self.mon.set_paused(False)
        self.mon.callback(None, -2, {"time": 1_000_000_000}, None)
        self.assertTrue(all(e["kind"] == "gap" for e in self.a.drain(2_000_000_000)))
        self.assertEqual(self.mon.status()["state"], "disabled")

    def test_callback_errors_are_fail_closed(self):
        self.mon.start()
        self.mon.context_provider = lambda apps: (_ for _ in ()).throw(RuntimeError("private data"))
        self.mon.callback(None, 10, {"time": 1_000_000_000}, None)
        self.assertTrue(all(e["kind"] == "gap" for e in self.a.drain(2_000_000_000)))
        self.assertNotIn("private data", str(self.mon.status()))

    def test_global_secure_input_unknown_or_active_denies_context(self):
        for state in (None, True):
            with patch("input_monitor.secure_input_enabled", return_value=state):
                self.assertIsNone(permitted_context({"com.microsoft.VSCode"}))

    def test_browser_and_unsupported_allowlists_are_rejected(self):
        with self.assertRaises(ValueError):
            InputMonitor(self.a, {"com.apple.Safari"}, lambda apps: dict(CTX), self.gaps.append)
