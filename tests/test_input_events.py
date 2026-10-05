import json
import unittest

from input_events import Aggregator


CTX = {"id": "context-1", "bundle_id": "com.microsoft.VSCode", "window_id": 7}


class InputEventTests(unittest.TestCase):
    def setUp(self):
        self.a = Aggregator("session", "2026-10-05T09:00:00+00:00", 0)

    def test_keyboard_burst_keeps_count_and_times_without_keys(self):
        self.a.feed("key", 0, CTX, {})
        self.a.feed("key", 200_000_000, CTX, {})
        self.assertEqual(self.a.drain(500_000_000), [])
        events = self.a.drain(1_000_000_000)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "keyboard_activity")
        self.assertEqual(events[0]["payload"], {"count": 2})
        self.assertEqual(events[0]["start_offset_ns"], 0)
        self.assertEqual(events[0]["end_offset_ns"], 200_000_000)

    def test_context_change_discards_pending_keyboard_detail(self):
        self.a.feed("key", 0, CTX, {})
        other = dict(CTX, id="context-2", window_id=8)
        self.a.feed("key", 100_000_000, other, {})
        events = self.a.drain(1_000_000_000)
        detail = [e for e in events if e["kind"] != "gap"]
        self.assertEqual(len(detail), 1)
        self.assertEqual(detail[0]["context_id"], "context-2")
        self.assertEqual(detail[0]["payload"]["count"], 1)

    def test_pointer_path_reduced_to_coarse_regions(self):
        self.a.feed("move", 0, CTX, {"region": "top-left"})
        self.a.feed("move", 100_000_000, CTX, {"region": "center"})
        self.a.feed("drag", 200_000_000, CTX, {"region": "bottom-right"})
        events = self.a.drain(1_000_000_000)
        self.assertEqual(events[0]["payload"], {"from": "top-left", "to": "bottom-right", "drag": True})
        self.assertNotIn("positions", json.dumps(events))

    def test_click_and_scroll_payloads_are_bounded(self):
        self.a.feed("click", 0, CTX, {"region": "center", "button": "left"})
        self.a.feed("scroll", 100_000_000, CTX, {"direction": "down", "magnitude": "small"})
        events = self.a.drain(1_000_000_000)
        self.assertEqual([e["kind"] for e in events], ["click", "scroll"])
        self.assertEqual(events[1]["payload"]["direction"], "down")

    def test_forbidden_or_unknown_payload_never_enters_state(self):
        for payload in ({"keycode": 1}, {"characters": "secret"}, {"modifiers": 4}, {"clipboard": "secret"}):
            with self.assertRaises(ValueError):
                self.a.feed("key", 0, CTX, payload)
        self.assertEqual(self.a.drain(1_000_000_000), [])

    def test_clear_removes_all_pending_detail(self):
        self.a.feed("key", 0, CTX, {})
        self.a.feed("click", 1, CTX, {"region": "center", "button": "left"})
        self.a.clear("paused")
        events = self.a.drain(1_000_000_000)
        self.assertTrue(events)
        self.assertTrue(all(e["kind"] == "gap" for e in events))
        self.assertNotIn("context-1", json.dumps(events))

    def test_order_and_buffer_overflow_are_visible_and_bounded(self):
        a = Aggregator("session", "2026-10-05T09:00:00+00:00", 0, max_summaries=3)
        for n in range(20):
            a.feed("click", n, CTX, {"region": "center", "button": "left"})
        events = a.drain(100)
        self.assertLessEqual(len(events), 3)
        self.assertIn("gap", [e["kind"] for e in events])
        self.assertEqual([e["sequence"] for e in events], sorted(e["sequence"] for e in events))

    def test_expired_and_backwards_events_become_gaps(self):
        self.a.feed("key", 1_000_000_000, CTX, {})
        events = self.a.drain(32_000_000_000)
        self.assertEqual([e["kind"] for e in events], ["gap"])
        self.a.feed("key", 34_000_000_000, CTX, {})
        self.a.feed("key", 33_000_000_000, CTX, {})
        events = self.a.drain(35_000_000_000)
        self.assertTrue(all(e["kind"] == "gap" for e in events))

    def test_equal_timestamps_use_sequence_and_utc_anchor(self):
        for _ in range(2):
            self.a.feed("click", 1_000_000_000, CTX, {"region": "center", "button": "left"})
        events = self.a.drain(2_000_000_000)
        self.assertEqual(events[0]["start_utc"], "2026-10-05T09:00:01+00:00")
        self.assertLess(events[0]["sequence"], events[1]["sequence"])
