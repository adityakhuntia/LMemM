"""Notes must retain their evidence and never silently attach to another context."""

import contextlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import dictation
import config
import macos
import notes
import store as memstore
import lmemm
import tracker
import resolver
from test_content import observation


def item():
    return {"id": "document-example", "app": "Google Docs", "kind": "document",
            "title": "Project plan", "doing": "Working on Project plan", "state": {}, "mostly": None,
            "activity": {c: {"seconds": 0, "text": []} for c in memstore.CATEGORIES},
            "first_seen": "2026-10-04T09:00:00", "last_seen": "2026-10-04T09:00:00",
            "seconds": 0, "visits": 1, "screenshot": "example.jpg", "ref": "example",
            "content": {"excerpts": [{"text": "Observed source text", "first_seen": "2026-10-04T09:00:00",
                         "last_seen": "2026-10-04T09:00:00", "source": {"app": "Safari"}}]}}


class DictationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(config.use_paths(self.root))
        self.mem = Path(config.paths().memory_dir)
        self.mem.mkdir(parents=True)
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))

    def test_legacy_store_migrates_without_losing_content_notes_or_numeric_timeline(self):
        old = item()
        old["notes"] = [{"at": "2026-10-04T09:01:00", "text": "Next: test migration."}]
        (self.mem / "memory.json").write_text(json.dumps({"items": [old]}))
        capture = tracker.Tracker()
        capture.events = [{"from": "09:00:00", "to": "09:00:10", "seconds": 10,
                           "item": old["id"], "app": old["app"], "doing": old["doing"],
                           "activity": {"reading": 10}, "trigger": "start", "_start": 1}]
        capture.save()
        self.assertEqual(memstore.load_items()[old["id"]], old)
        public = json.loads((self.mem / "memory.json").read_text())
        self.assertEqual(public["schema_version"], 3)
        self.assertEqual(public["things"][0]["content"], old["content"])
        self.assertEqual(public["things"][0]["your_notes"][0]["text"], "Next: test migration.")
        timeline = json.loads(next((self.mem / "sessions").glob("*.json")).read_text())["timeline"]
        self.assertEqual(timeline[0]["item"], old["id"])
        self.assertEqual(timeline[0]["memory"], old["id"])
        self.assertEqual(timeline[0]["seconds"], 10)
        self.assertEqual(timeline[0]["activity"], {"reading": 10})

    def test_corrupt_memory_file_is_not_silently_replaced_with_empty_memory(self):
        (self.mem / "memory.json").write_text("not json")
        with self.assertRaises(ValueError):
            tracker.Tracker()
        self.assertEqual((self.mem / "memory.json").read_text(), "not json")

    def test_a_things_only_memory_file_is_not_treated_as_empty(self):
        # a readable-only export, missing the full "items" list needed to resume
        (self.mem / "memory.json").write_text(json.dumps({"things": [{"id": "valuable"}]}))
        with self.assertRaises(ValueError):
            tracker.Tracker()

    def test_blocked_capture_does_not_open_panel_for_previous_item(self):
        capture = tracker.Tracker()
        old = item()
        capture.items = {old["id"]: old}
        capture.events = [{"item": old["id"], "_raw": ("Safari", "Same title")}]
        shown = []
        with patch.object(macos, "front", return_value={"app": "Safari", "window": "Same title"}), \
             patch.object(capture, "capture", return_value=None), \
             patch.object(capture.panel, "show", side_effect=lambda *args: shown.append(args)):
            self.assertFalse(capture.open_note())
        self.assertEqual(shown, [])
        self.assertNotIn("notes", old)

    def test_note_waiting_for_ocr_is_persisted_without_blocking_and_attaches_later(self):
        capture = tracker.Tracker()
        old = item()
        capture.items = {old["id"]: old}
        with patch.object(tracker.time, "sleep", side_effect=AssertionError("UI must not block")):
            capture.save_note(("frame", "fresh-frame"), "Next: test migration.")
        self.assertNotIn("notes", old)
        saved = json.loads(next((self.mem / "sessions").glob("*.json")).read_text())
        self.assertEqual(saved["notes"][0]["status"], "pending")
        capture.frame_item["fresh-frame"] = old["id"]
        notes.attach_pending(capture.items, capture.frame_item, capture.notes)
        capture.save()
        self.assertEqual(old["notes"][0]["text"], "Next: test migration.")
        self.assertEqual(capture.notes[0]["item"], old["id"])
        self.assertEqual(capture.notes[0]["status"], "attached")

    def test_worker_ocr_does_not_block_note_save_and_attaches_after_resolution(self):
        capture = tracker.Tracker()
        res, meta = observation("Observed document content")
        meta.update(ts="20261005-090000", image="20261005-090000.jpg")
        path = self.root / "20261005-090000.json"
        path.write_text(json.dumps(meta))
        Image.new("RGB", (1000, 800), "white").save(self.root / meta["image"])
        started, release, saved = threading.Event(), threading.Event(), threading.Event()

        def slow_ocr(_):
            started.set()
            release.wait(timeout=5)
            return res

        def save():
            capture.save_note(("frame", meta["ts"]), "Next: test migration.")
            saved.set()

        with config.use_paths(self.root), patch.object(resolver, "resolve", side_effect=slow_ocr):
            capture.q.put((str(path), meta, "note", True))
            capture.q.put(None)
            worker = threading.Thread(target=capture.worker)
            writer = threading.Thread(target=save)
            worker.start()
            try:
                self.assertTrue(started.wait(timeout=2))
                writer.start()
                self.assertTrue(saved.wait(timeout=1), "Saving a note blocked on the OCR worker")
            finally:
                release.set()
                worker.join(timeout=3)
                if writer.ident:
                    writer.join(timeout=3)
        self.assertEqual(len(capture.items), 1)
        memory = next(iter(memstore.load_items().values()))
        self.assertEqual(memory["notes"][0]["text"], "Next: test migration.")
        self.assertEqual(capture.notes[0]["status"], "attached")

    def test_note_cli_shows_notes_and_content_with_legacy_session(self):
        old = item()
        old["notes"] = [{"at": "2026-10-04T09:01:00", "text": "Next: test migration."}]
        (self.mem / "memory.json").write_text(json.dumps({"items": [old]}))
        (self.mem / "sessions").mkdir()
        (self.mem / "sessions" / "old.json").write_text(json.dumps({"session": "old", "timeline": [
            {"from": "09:00:00", "seconds": 10, "app": old["app"], "doing": old["doing"]}]}))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            lmemm.show_memory(1, show_content=True)
        self.assertIn("Next: test migration.", output.getvalue())
        self.assertIn("Observed source text", output.getvalue())
        self.assertIn("10s", output.getvalue())


class ListenerCleanupTests(unittest.TestCase):
    def test_stop_removes_transcript_errors_and_cancelled_note_files(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "lmemm-test"
            directory.mkdir()
            out = directory / "transcript.txt"
            out.write_text("private draft")
            Path(str(out) + ".error").write_text("error")
            Path(str(out) + ".done").touch()
            listener = dictation.Listener()
            listener.out = str(out)
            self.assertEqual(listener.stop(wait=0), "private draft")
            self.assertFalse(directory.exists())
            self.assertEqual(listener.stop(wait=0), "")


if __name__ == "__main__":
    unittest.main()
