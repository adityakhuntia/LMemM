import copy
import json
import tempfile
import unittest
from pathlib import Path

from input_events import Aggregator
from input_store import InputStore, plan_session_deletion, delete_session
from test_dictation_integration import item


class InputStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = "2026-10-05T09:00:00+00:00"
        self.a = Aggregator("first", self.now, 0)
        self.ctx = {"id": "context", "bundle_id": "com.microsoft.VSCode", "window_id": 7}

    def click(self, ns=0):
        self.a.feed("click", ns, self.ctx, {"region": "center", "button": "left"})
        return self.a.drain(ns)

    def test_private_store_retention_and_capture_link(self):
        store = InputStore("first", self.root, clock=lambda: self.now)
        store.append(self.click())
        store.link_capture("capture", "context", 10, 20, "document-example")
        events = store.read()["events"]
        self.assertEqual(events[0]["after_capture"], "capture")
        self.assertEqual(events[0]["item"], "document-example")
        self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
        self.now = "2026-10-06T09:00:01+00:00"
        self.assertEqual(store.read()["events"], [])

    def test_wrong_context_and_closed_store_cannot_link_or_write(self):
        store = InputStore("first", self.root, clock=lambda: self.now)
        store.append(self.click())
        store.link_capture("wrong", "different-context", 10, 20, "wrong-item")
        self.assertNotIn("item", store.read()["events"][0])
        store.close()
        with self.assertRaises(RuntimeError):
            store.append(self.click(100))

    def test_invalid_retention_and_corruption_fail_closed(self):
        for hours in (0, -1, 25):
            with self.assertRaises(ValueError):
                InputStore("first", self.root, retention_hours=hours)
        store = InputStore("first", self.root, clock=lambda: self.now)
        store.path.write_text("invalid")
        with self.assertRaises(ValueError):
            InputStore("first", self.root, clock=lambda: self.now)

    def test_deletion_preserves_baseline_and_other_session_contributions(self):
        baseline = item()
        paths = {"data_dir": self.root, "memory_dir": self.root / "memory", "pidfile": self.root / "pid"}
        store1 = InputStore("first", self.root / "memory", clock=lambda: self.now)
        store1.initialize_baseline({baseline["id"]: baseline})
        after1 = copy.deepcopy(baseline)
        after1.update(seconds=10, visits=2, last_seen="2026-10-05T09:00:00")
        after1["notes"] = [{"at": "2026-10-05T09:00:00", "text": "First note"}]
        store1.checkpoint({baseline["id"]: after1}, [], [])
        store1.close()
        store2 = InputStore("second", self.root / "memory", clock=lambda: self.now)
        store2.initialize_baseline({baseline["id"]: after1})
        after2 = copy.deepcopy(after1)
        after2.update(seconds=25, visits=3, last_seen="2026-10-05T09:01:00")
        after2["notes"].append({"at": "2026-10-05T09:01:00", "text": "Second note"})
        store2.checkpoint({baseline["id"]: after2}, [], [])
        store2.close()
        plan = plan_session_deletion("first", paths)
        self.assertEqual(plan["blockers"], [])
        delete_session("first", paths)
        restored = json.loads((self.root / "memory" / ".index.json").read_text())["items"][0]
        self.assertEqual(restored["seconds"], 15)
        self.assertEqual(restored["visits"], 2)
        self.assertEqual([n["text"] for n in restored["notes"]], ["Second note"])
        self.assertFalse(store1.path.exists())
        self.assertTrue(store2.path.exists())

    def test_legacy_or_traversal_or_active_deletion_is_blocked_before_changes(self):
        paths = {"data_dir": self.root, "memory_dir": self.root / "memory", "pidfile": self.root / "pid"}
        with self.assertRaises(ValueError):
            plan_session_deletion("../secret", paths)
        plan = plan_session_deletion("legacy", paths)
        self.assertTrue(plan["blockers"])
        with self.assertRaises(ValueError):
            delete_session("legacy", paths)

    def test_unknown_fields_are_rejected_not_stored(self):
        store = InputStore("first", self.root, clock=lambda: self.now)
        event = self.click()[0]
        event["characters"] = "secret"
        with self.assertRaises(ValueError):
            store.append([event])
        self.assertEqual(store.read()["events"], [])

    def test_boundary_prevents_later_capture_from_linking_earlier_event(self):
        store = InputStore("first", self.root, clock=lambda: self.now)
        store.append(self.click())
        store.invalidate_context("paused")
        store.link_capture("later", "context", 10, 20, "item")
        self.assertNotIn("after_capture", store.read()["events"][0])

    def test_startup_prunes_previous_session_details(self):
        store = InputStore("first", self.root, clock=lambda: self.now)
        store.append(self.click())
        store.close()
        self.now = "2026-10-06T09:00:01+00:00"
        InputStore("second", self.root, clock=lambda: self.now)
        self.assertEqual(json.loads(store.path.read_text())["events"], [])

    def test_boundary_keeps_verified_source_image_but_never_uses_it_as_before(self):
        store = InputStore("first", self.root, clock=lambda: self.now)
        source = self.root / "source.jpg"
        source.write_bytes(b"image")
        store.link_capture("20261005-090000", "context", 0, 10)
        store.keep_capture("20261005-090000", source)
        store.invalidate_context("paused")
        store.append(self.click(20))
        store.link_capture("20261005-090001", "context", 30, 40)
        self.assertNotIn("before_capture", store.read()["events"][0])
        self.assertTrue((self.root / "inputs/frames/first/20261005-090000.jpg").exists())

    def test_repeated_deletion_remains_reconstructable(self):
        baseline = item()
        paths = {"data_dir": self.root, "memory_dir": self.root / "memory", "pidfile": self.root / "pid"}
        current = {baseline["id"]: baseline}
        for name, seconds in (("first", 10), ("second", 25)):
            store = InputStore(name, paths["memory_dir"], clock=lambda: self.now)
            store.initialize_baseline(current)
            current = copy.deepcopy(current)
            current[baseline["id"]]["seconds"] = seconds
            store.checkpoint(current, [], [])
            store.close()
        delete_session("first", paths)
        self.assertEqual(plan_session_deletion("second", paths)["blockers"], [])
        delete_session("second", paths)
        self.assertEqual(json.loads((paths["memory_dir"] / ".index.json").read_text())["items"][0]["seconds"], 0)

    def test_deletion_scrubs_all_retained_checkpoints_and_inherited_pin(self):
        base = item()
        paths = {"data_dir": self.root, "memory_dir": self.root / "memory", "pidfile": self.root / "pid"}
        current = {}
        for name, seconds in (("first", 10), ("second", 20), ("third", 30)):
            store = InputStore(name, paths["memory_dir"], clock=lambda: self.now)
            store.initialize_baseline(current)
            current = copy.deepcopy(current) or {base["id"]: copy.deepcopy(base)}
            current[base["id"]].update(seconds=seconds, last_seen=f"2026-10-05T09:0{seconds//10}:00", pinned=True)
            current[base["id"]]["notes"] = [{"at": "2026-10-05T09:01:00", "text": "ONLY_FIRST_SECRET"}]
            store.checkpoint(current, [], [])
            store.close()
        delete_session("first", paths)
        for path in (paths["memory_dir"] / "contributions").glob("*.json"):
            self.assertNotIn("ONLY_FIRST_SECRET", path.read_text())
        restored = json.loads((paths["memory_dir"] / ".index.json").read_text())["items"][0]
        self.assertNotIn("pinned", restored)
        self.assertEqual(restored["first_seen"], "2026-10-05T09:02:00")

    def test_pending_deletion_cannot_be_overwritten_by_new_dry_run(self):
        from input_store import private_write
        paths = {"data_dir": self.root, "memory_dir": self.root / "memory", "pidfile": self.root / "pid"}
        private_write(paths["memory_dir"] / ".deletion.json", {"pending": True})
        plan = plan_session_deletion("another", paths)
        self.assertTrue(any("pending" in b.lower() for b in plan["blockers"]))

    def test_periodic_read_prunes_old_sessions_and_counts_capacity_loss(self):
        first = InputStore("first", self.root, clock=lambda: self.now)
        first.append(self.click())
        second = InputStore("second", self.root, clock=lambda: self.now)
        self.now = "2026-10-06T09:00:01+00:00"
        second.read()
        self.assertEqual(json.loads(first.path.read_text())["events"], [])
        self.now = "2026-10-05T09:00:00+00:00"
        first.append([self.click(ns)[0] for ns in range(4097)])
        self.assertGreaterEqual(first.read().get("dropped_capacity", 0), 1)

    def test_shared_source_screenshot_blocks_deletion_without_mutation(self):
        baseline = item()
        paths = {"data_dir": self.root, "memory_dir": self.root / "memory", "pidfile": self.root / "pid"}
        current = {}
        image = self.root / "20261005-090000.jpg"
        image.write_bytes(b"source")
        (self.root / "20261005-090000.json").write_text(json.dumps({"session": "first", "image": image.name}))
        for name, seconds in (("first", 10), ("second", 20)):
            store = InputStore(name, paths["memory_dir"], clock=lambda: self.now)
            store.initialize_baseline(current)
            current = copy.deepcopy(current) or {baseline["id"]: copy.deepcopy(baseline)}
            current[baseline["id"]].update(seconds=seconds, screenshot=image.name)
            store.checkpoint(current, [], [])
            store.close()
        plan = plan_session_deletion("first", paths)
        self.assertTrue(any("screenshot" in b.lower() for b in plan["blockers"]))
        with self.assertRaises(ValueError):
            delete_session("first", paths)
        self.assertTrue(image.exists())

    def test_interrupted_deletion_recovers_on_memory_load_before_new_session(self):
        from unittest.mock import patch
        import tracker
        baseline = item()
        paths = {"data_dir": self.root, "memory_dir": self.root / "memory", "pidfile": self.root / "pid"}
        current = {baseline["id"]: baseline}
        for name, seconds in (("first", 10), ("second", 20)):
            store = InputStore(name, paths["memory_dir"], clock=lambda: self.now)
            store.initialize_baseline(current)
            current = copy.deepcopy(current)
            current[baseline["id"]]["seconds"] = seconds
            store.checkpoint(current, [], [])
            store.close()
        unlink = Path.unlink
        def interrupted(path, *args, **kwargs):
            if path.resolve() == (paths["memory_dir"] / "contributions/first.json").resolve():
                raise OSError("simulated interruption")
            return unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", interrupted), self.assertRaises(OSError):
            delete_session("first", paths)
        with patch.object(tracker, "ITEMS_FILE", str(paths["memory_dir"] / "memory.json")), patch.object(tracker, "INTERNAL_FILE", str(paths["memory_dir"] / ".index.json")):
            restored = tracker.load_items()
        self.assertEqual(restored[baseline["id"]]["seconds"], 10)
        self.assertFalse((paths["memory_dir"] / ".deletion.json").exists())
        delete_session("second", paths)
        self.assertEqual(json.loads((paths["memory_dir"] / ".index.json").read_text())["items"][0]["seconds"], 0)
