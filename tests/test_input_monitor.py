import unittest
import tracker
from unittest.mock import patch

from input_events import Aggregator
from input_monitor import InputMonitor, permitted_context


class Native:
    kCGSessionEventTap = 1
    kCGAnnotatedSessionEventTap = 2
    kCGEventTargetUnixProcessID = 40
    kCGHeadInsertEventTap = 0
    kCGEventTapOptionListenOnly = 1
    kCGEventKeyDown = 10
    kCGKeyboardEventKeycode = 9
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
        if field == 40: return 42
        if field not in (11, 12): raise AssertionError("key field read")
        return -5 if field == 11 else 0


CTX = {"id": "context", "bundle_id": "com.microsoft.VSCode", "window_id": 7, "pid": 42,
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

    def test_pointer_just_outside_window_is_rejected(self):
        self.mon.start()
        self.native.CGEventGetLocation = lambda event: type("Point", (), {"x": -0.1, "y": 50})()
        self.mon.callback(None, 1, {"time": 1_000_000_000}, None)
        self.assertTrue(all(e["kind"] == "gap" for e in self.a.drain(2_000_000_000)))

    def test_target_process_mismatch_is_never_attributed_to_foreground(self):
        self.mon.start()
        original = self.native.CGEventGetIntegerValueField
        self.native.CGEventGetIntegerValueField = lambda event, field: 999 if field == 40 else original(event, field)
        self.mon.callback(None, 10, {"time": 1_000_000_000}, None)
        self.assertTrue(all(e["kind"] == "gap" for e in self.a.drain(2_000_000_000)))

    def test_event_predating_verified_window_boundary_is_discarded(self):
        self.mon.start()
        self.mon.clock = lambda: 1_050_000_000
        changed = dict(CTX, id="new-window", window_id=8)
        self.mon.verify_context(changed)
        self.mon.context_provider = lambda apps: changed
        self.mon.callback(None, 10, {"time": 1_000_000_000}, None)
        self.assertTrue(all(e["kind"] == "gap" for e in self.a.drain(2_000_000_000)))

    def test_focus_inspection_rejects_secure_missing_owner_and_unknown_role(self):
        import sys
        from types import SimpleNamespace
        foreground = {"pid": 42, "win_id": 7, "window": "Project", "bundle_id": "com.microsoft.VSCode", "bounds": CTX["bounds"]}
        def attributes(element, name, unused):
            return {"AXFocusedUIElement": (0, "element"), "AXRole": (0, "AXTextArea"), "AXSubrole": (-25205, None)}[name]
        native = SimpleNamespace(AXIsProcessTrusted=lambda: True, AXUIElementCreateSystemWide=lambda: "system",
                                 AXUIElementCopyAttributeValue=attributes, AXUIElementGetPid=lambda *args: (0, 42))
        with patch.dict(sys.modules, {"ApplicationServices": native}), patch("tracker.front", return_value=foreground), patch("input_monitor.secure_input_enabled", return_value=False):
            self.assertIsNotNone(permitted_context({"com.microsoft.VSCode"}))
            for owner in ((0, 43), (-1, 42)):
                native.AXUIElementGetPid = lambda *args: owner
                self.assertIsNone(permitted_context({"com.microsoft.VSCode"}))
            native.AXUIElementGetPid = lambda *args: (0, 42)
            for role, sub in (("AXTextField", "AXSecureTextField"), ("unknown", None), (None, None)):
                native.AXUIElementCopyAttributeValue = lambda element, name, unused: (0, "element" if name == "AXFocusedUIElement" else role if name == "AXRole" else sub)
                self.assertIsNone(permitted_context({"com.microsoft.VSCode"}))

    def test_vscode_accessibility_is_enabled_only_for_opted_in_foreground_app(self):
        import input_monitor
        from types import SimpleNamespace
        calls = []
        flag = {"enabled": False}
        def set_attribute(app, attr, value):
            calls.append((app, attr, value))
            flag["enabled"] = value
            return 0
        native = SimpleNamespace(AXUIElementCreateApplication=lambda pid: pid,
                                 AXUIElementCopyAttributeValue=lambda *args: (0, flag["enabled"]),
                                 AXUIElementSetAttributeValue=set_attribute)
        support = input_monitor.AccessibilitySupport(native)
        support.ensure({"pid": 42, "bundle_id": "com.microsoft.VSCode"}, {"com.microsoft.VSCode"})
        support.ensure({"pid": 42, "bundle_id": "com.microsoft.VSCode"}, {"com.microsoft.VSCode"})
        support.ensure({"pid": 43, "bundle_id": "com.apple.Safari"}, {"com.microsoft.VSCode"})
        self.assertEqual(calls, [(42, "AXManualAccessibility", True)])
        support.restore()
        self.assertEqual(calls[-1], (42, "AXManualAccessibility", False))

    def test_native_no_subrole_value_is_not_an_unknown_or_secure_field(self):
        import sys
        from types import SimpleNamespace
        foreground = {"pid": 42, "win_id": 7, "window": "Project", "bundle_id": "com.microsoft.VSCode", "bounds": CTX["bounds"]}
        def attributes(element, name, unused):
            return {"AXFocusedUIElement": (0, "element"), "AXRole": (0, "AXTextArea"), "AXSubrole": (-25212, None)}[name]
        native = SimpleNamespace(AXIsProcessTrusted=lambda: True, AXUIElementCreateSystemWide=lambda: "system", AXUIElementCopyAttributeValue=attributes, AXUIElementGetPid=lambda *args: (0, 42))
        with patch.dict(sys.modules, {"ApplicationServices": native}), patch("tracker.front", return_value=foreground), patch("input_monitor.secure_input_enabled", return_value=False):
            self.assertIsNotNone(permitted_context({"com.microsoft.VSCode"}))

    def test_only_allowlisted_tab_shortcuts_emit_classified_steps_without_raw_keys(self):
        self.mon.start()
        self.native.CGEventGetFlags = lambda event: 1 << 18
        original = self.native.CGEventGetIntegerValueField
        self.native.CGEventGetIntegerValueField = lambda event, field: 48 if field == 9 else original(event, field)
        self.mon.callback(None, 10, {"time": 1_000_000_000}, None)
        events = self.a.drain(2_000_000_000)
        shortcut = next(e for e in events if e['kind'] == 'navigation_shortcut')
        self.assertEqual(shortcut['payload'], {'action':'tab_switch','direction':'forward','count':1})
        self.assertNotIn('keycode', str(shortcut))
        self.native.CGEventGetFlags = lambda event: (1 << 20) | (1 << 17)
        self.mon.callback(None, 10, {"time": 1_000_000_000}, None)
        shortcut = next(e for e in self.a.drain(2_000_000_000) if e['kind'] == 'navigation_shortcut')
        self.assertEqual(shortcut['payload']['action'], 'app_switch')
        self.assertEqual(shortcut['payload']['direction'], 'backward')

    def test_non_tab_command_has_no_navigation_or_raw_key_payload(self):
        self.mon.start()
        self.native.CGEventGetFlags=lambda event:1 << 20
        original=self.native.CGEventGetIntegerValueField
        self.native.CGEventGetIntegerValueField=lambda event,field:0 if field==9 else original(event,field)
        self.mon.callback(None,10,{'time':1_000_000_000},None)
        events=self.a.drain(2_000_000_000)
        self.assertEqual([e['kind'] for e in events],['keyboard_activity'])
        self.assertEqual(events[0]['payload'],{'count':1})
