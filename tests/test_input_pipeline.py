import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
import tracker
from input_store import private_write
from input_monitor import context_id


class InputPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(config.use_paths(self.root))
        self.mem = Path(config.paths().memory_dir)

    def test_default_capture_does_not_create_monitor_or_input_store(self):
        capture = tracker.Tracker()
        self.assertIsNone(capture.input_monitor)
        self.assertFalse((self.mem / "inputs").exists())

    def test_input_summaries_trigger_debounced_capture_and_persist(self):
        capture = tracker.Tracker(input_apps={"com.microsoft.VSCode"})
        capture.input_monitor.state = "recording"
        ctx = {"id": "context", "bundle_id": "com.microsoft.VSCode", "window_id": 7, "bounds": {}}
        origin = capture.input_aggregator.origin_ns
        capture.input_aggregator.feed("click", origin, ctx, {"region": "center", "button": "left"})
        capture.input_monitor.context_provider = lambda apps: ctx
        capture.poll_input()
        self.assertEqual(capture.pending[0], "input_activity")
        doc = capture.input_store.read()
        self.assertEqual(doc["events"][0]["kind"], "click")

    def test_pause_clears_input_and_stops_even_pinned_capture(self):
        capture = tracker.Tracker(input_apps={"com.microsoft.VSCode"})
        ctx = {"id": "context", "bundle_id": "com.microsoft.VSCode", "window_id": 7}
        capture.input_aggregator.feed("key", capture.input_aggregator.origin_ns, ctx, {})
        capture.set_manual_pause(True)
        self.assertIsNone(capture.capture("pin", pinned=True))
        self.assertTrue(all(e["kind"] == "gap" for e in capture.input_aggregator.drain(capture.input_aggregator.origin_ns + 1_000_000_000)))
        capture.set_manual_pause(False)
        self.assertFalse(capture.manual_paused)

    def test_excluded_context_clears_pending_detail_and_link_history(self):
        capture = tracker.Tracker(input_apps={"com.microsoft.VSCode"})
        capture.input_monitor.state = "recording"
        ctx = {"id": "context", "bundle_id": "com.microsoft.VSCode", "window_id": 7}
        capture.input_aggregator.feed("key", capture.input_aggregator.origin_ns, ctx, {})
        capture.input_monitor.context_provider = lambda apps: None
        capture.poll_input()
        self.assertTrue(all(e["kind"] == "gap" for e in capture.input_store.read()["events"]))
        self.assertEqual(capture.input_store.status()["gap"], "protected_or_excluded")

    def test_notes_and_flags_also_gate_input(self):
        capture = tracker.Tracker(input_apps={"com.microsoft.VSCode"})
        capture.set_flag("locked", True)
        self.assertTrue(capture.input_monitor.paused)
        self.assertIsNone(capture.capture("timer"))

    def test_control_file_is_pid_scoped(self):
        capture = tracker.Tracker()
        private_write(capture.control_file, {"pid": -1, "action": "pause"})
        capture.process_control()
        self.assertFalse(capture.manual_paused)

    def test_closed_session_drops_late_ocr_before_any_memory_mutation(self):
        capture = tracker.Tracker(input_apps={"com.microsoft.VSCode"})
        capture.input_store.close()
        capture.remember({}, "timer", False, 0, None, None, None, None, None, None)
        self.assertEqual(capture.items, {})
        self.assertEqual(capture.events, [])

    def test_status_updates_and_invalid_control_file_cannot_kill_capture(self):
        capture = tracker.Tracker(input_apps={"com.microsoft.VSCode"})
        capture.control_file.write_text("invalid")
        capture.process_control()
        capture.input_monitor.state = "disabled"
        capture.input_monitor.context_provider = lambda apps: None
        capture.poll_input()
        self.assertEqual(json.loads(capture.status_file.read_text())["input"]["state"], "disabled")

    def test_confirmed_allowed_context_change_is_visible_and_invalidates_links(self):
        capture = tracker.Tracker(input_apps={"com.microsoft.VSCode"})
        capture.input_monitor.state = "recording"
        capture.input_context = {"id": "old"}
        ctx = {"id": "new", "bundle_id": "com.microsoft.VSCode", "window_id": 7, "pid": 42}
        capture.input_monitor.context_provider = lambda apps: ctx
        capture.poll_input()
        transitions = [e for e in capture.input_store.read()["events"] if e["kind"] == "context_transition"]
        self.assertEqual(transitions[0]["payload"], {"from": "old", "to": "new"})

    def test_unavailable_collector_preserves_permission_failure_reason(self):
        capture = tracker.Tracker(input_apps={"com.microsoft.VSCode"})
        capture.input_monitor.state = "unavailable"
        capture.input_monitor._gap("input_permission")
        capture.input_monitor.context_provider = lambda apps: None
        capture.poll_input()
        self.assertEqual(capture.input_store.status()["gap"], "input_permission")
