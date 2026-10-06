import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
import lmemm
import tracker
from input_store import InputStore
from input_events import Aggregator


class InputCliTests(unittest.TestCase):
    def test_input_flags_require_explicit_supported_app(self):
        for args in (["--input-events"], ["--input-app", "com.microsoft.VSCode"],
                     ["--input-events", "--input-app", "com.apple.Safari"],
                     ["--input-events", "--input-app", "com.microsoft.VSCode", "--input-retention-hours", "25"]):
            with self.subTest(args=args), patch("sys.argv", ["lmemm.py", *args]), \
                 patch.object(tracker.Tracker, "run", side_effect=AssertionError("invalid flags started capture")):
                with self.assertRaises(SystemExit):
                    lmemm.main()

    def test_valid_flags_pass_to_tracker_without_starting_real_monitor(self):
        created = []
        class Capture:
            def __init__(self, **kwargs): created.append(kwargs)
            def run(self): pass
        with patch.object(tracker, "Tracker", Capture), patch("sys.argv", ["lmemm.py", "--input-events", "--input-app", "com.microsoft.VSCode"]):
            lmemm.main()
        self.assertEqual(created[0]["input_apps"], {"com.microsoft.VSCode"})

    def test_events_can_be_inspected_without_recognized_memory_items(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(stack.enter_context(config.use_paths(directory)).memory_dir)
            store = InputStore("test", root)
            import datetime
            a = Aggregator("test", datetime.datetime.now(datetime.timezone.utc).isoformat(), 0)
            a.feed("key", 0, {"id": "context"}, {})
            store.append(a.drain(1_000_000_000))
            output = io.StringIO()
            with patch("sys.argv", ["lmemm.py", "memory", "--events"]), contextlib.redirect_stdout(output):
                lmemm.main()
            self.assertIn("keyboard activity", output.getvalue())
            self.assertIn("1 events", output.getvalue())

    def test_pause_command_targets_running_pid_and_stale_status_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, config.use_paths(directory) as paths:
            Path(paths.pidfile).write_text(str(os.getpid()))
            output = io.StringIO()
            with patch("sys.argv", ["lmemm.py", "pause"]), contextlib.redirect_stdout(output):
                lmemm.main()
            control = Path(paths.control_file)
            self.assertEqual(json.loads(control.read_text()), {"pid": os.getpid(), "action": "pause"})

    def test_stale_status_and_mismatched_deletion_confirmation_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory, config.use_paths(directory) as paths:
            Path(paths.pidfile).write_text(str(os.getpid()))
            Path(paths.status_file).write_text(json.dumps({"pid": -1}))
            with patch("sys.argv", ["lmemm.py", "status"]), self.assertRaises(SystemExit):
                lmemm.main()
            with patch("sys.argv", ["lmemm.py", "delete-session", "first", "--confirm", "second"]), self.assertRaises(SystemExit):
                lmemm.main()

    def test_deletion_dry_run_shows_legacy_blockers_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory)
            stack.enter_context(config.use_paths(root))
            output = io.StringIO()
            with patch("sys.argv", ["lmemm.py", "delete-session", "legacy", "--dry-run"]), contextlib.redirect_stdout(output):
                lmemm.main()
            self.assertIn("provenance", output.getvalue())
            self.assertEqual(list(root.iterdir()), [])
