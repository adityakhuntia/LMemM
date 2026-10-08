"""The interactive menu (`lmemm.py` with no arguments): one front door to every command."""

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
import store
import tracker
from test_notes import item as note_item


def run(inputs):
    """Feed `inputs` (a list of lines) to the menu; return everything it printed."""
    fed = iter(inputs)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        lmemm.interactive_menu(read=lambda prompt="": next(fed), write=print)
    return out.getvalue()


class MenuShapeTests(unittest.TestCase):
    def test_every_item_has_a_unique_key_and_a_working_action(self):
        keys = [item.key for item in lmemm.MENU]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertNotIn("0", keys)                                # 0 is always "quit", not a listed item
        for item in lmemm.MENU:
            self.assertTrue(callable(item.action))

    def test_menu_text_lists_every_item_and_quit(self):
        text = lmemm.menu_text()
        for item in lmemm.MENU:
            self.assertIn(item.key, text)
            self.assertIn(item.label, text)
        self.assertIn("0  Quit", text)


class MenuFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.paths = self.stack.enter_context(config.use_paths(self.tmp.name))

    def test_quit_immediately_prints_the_menu_once_and_stops(self):
        text = run(["0"])
        self.assertEqual(text.count("LMemM\n─────"), 1)

    def test_blank_lines_are_ignored_and_an_unknown_choice_does_not_crash_the_loop(self):
        text = run(["", "99", "0"])
        self.assertIn("isn't one of the options above", text)
        self.assertEqual(text.count("LMemM\n─────"), 1)            # still only shown once; it's a loop, not a crash

    def test_ctrl_d_and_ctrl_c_leave_cleanly(self):
        for exc in (EOFError, KeyboardInterrupt):
            with self.subTest(exc=exc):
                def raiser(prompt=""):
                    raise exc
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    lmemm.interactive_menu(read=raiser, write=print)
                self.assertEqual(out.getvalue().count("LMemM\n─────"), 1)

    def test_an_action_that_sys_exits_is_caught_and_the_menu_continues(self):
        text = run(["2", "", "0"])                                 # memory, with nothing remembered yet
        self.assertIn("nothing remembered yet", text)
        self.assertEqual(text.count("LMemM\n─────"), 2)            # it looped back, not crashed out

    def test_memory_with_args_and_without_behave_like_the_cli(self):
        items = {"a": note_item("a", note_texts=["x"])}
        store.save_memory(items)
        with_args = run(["2", "1", "0"])
        bare = run(["2", "", "0"])
        self.assertIn("remembered (most recent first)", with_args)
        self.assertIn("remembered (most recent first)", bare)

    def test_pending_edits_shows_your_actual_notes(self):
        items = {"a": note_item("a", title="Q3 plan", note_texts=["add pricing"])}
        store.save_memory(items)
        text = run(["3", "", "0"])
        self.assertIn("add pricing", text)

    def test_context_export_runs_through_the_menu(self):
        items = {"a": note_item("a", title="Q3 plan", note_texts=["add pricing"])}
        store.save_memory(items)
        store.save_session("s1", [{"from": "10:00", "to": "10:05", "seconds": 300, "item": "a",
                                   "app": "Google Docs", "doing": "x", "activity": {}, "trigger": "timer"}], [])
        text = run(["4", "", "0"])
        self.assertIn('"things": 1', text)

    def test_status_when_nothing_is_running_is_a_clean_message_not_a_crash(self):
        text = run(["5", "0"])
        self.assertIn("tracker is not running", text)
        self.assertEqual(text.count("LMemM\n─────"), 2)

    def test_pause_resume_toggles_by_reading_current_status(self):
        Path(self.paths.pidfile).write_text(str(os.getpid()))
        self.addCleanup(lambda: Path(self.paths.pidfile).unlink(missing_ok=True))
        text = run(["6", "0"])
        self.assertIn("pause requested", text)
        control = json.loads(Path(self.paths.control_file).read_text())
        self.assertEqual(control["action"], "pause")

    def test_note_and_pin_report_cleanly_when_nothing_is_running(self):
        text = run(["7", "0"])
        self.assertIn("isn't running", text)
        text = run(["8", "0"])
        self.assertIn("isn't running", text)

    def test_delete_session_prompts_for_its_own_arguments(self):
        text = run(["9", "missing --dry-run", "0"])
        self.assertIn("has no reconstructable provenance", text)

    def test_bare_cli_invocation_enters_the_menu(self):
        with patch("sys.argv", ["lmemm.py"]), patch.object(lmemm, "interactive_menu") as entry:
            lmemm.main()
        entry.assert_called_once_with()

    def test_explicit_menu_subcommand_also_enters_the_menu(self):
        with patch("sys.argv", ["lmemm.py", "menu"]), patch.object(lmemm, "interactive_menu") as entry:
            lmemm.main()
        entry.assert_called_once_with()

    def test_an_explicit_subcommand_still_bypasses_the_menu(self):
        with patch("sys.argv", ["lmemm.py", "status"]), patch.object(lmemm, "interactive_menu") as entry, \
             self.assertRaises(SystemExit):
            lmemm.main()
        entry.assert_not_called()

    def test_start_is_reachable_from_the_menu_without_actually_starting_capture(self):
        calls = []
        with patch.object(tracker, "Tracker", lambda **kw: calls.append(kw) or type("T", (), {"run": lambda self: None})()):
            run(["1", "--every 10 --no-widget", "0"])
        self.assertEqual(calls[0]["every"], 10)
        self.assertFalse(calls[0]["show_widget"])


if __name__ == "__main__":
    unittest.main()
