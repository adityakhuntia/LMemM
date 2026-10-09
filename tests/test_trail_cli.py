import contextlib
import io
import json
import os
import py_compile
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import config
import trail_cli
from test_trail import Node, text
from trail_store import TrailStore


def out(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a, **k)
    return buf.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = TrailStore(os.path.join(self.tmp.name, "trail"), "t")
        place = {"key": "WhatsApp:chat:mum", "kind": "chat", "name": "Mum", "service": "WhatsApp",
                 "signals": ["box", "selected"], "confidence": 0.95, "conflict": False}
        self.store.add("app_switch", app="WhatsApp", bundle_id="x")
        self.store.add("focus", app="WhatsApp", place=place, dwell_ms=0)
        self.store.add("text", place="WhatsApp:chat:mum", source="ax", added=["hi", "there"], removed=0, total=2)
        self.store.add("typing", place="WhatsApp:chat:mum", n=5, ms=900, field="Type a message to Mum")
        self.store.add("click", place="WhatsApp:chat:mum", button="left", role="AXButton", target="Send")
        self.store.add("gap", reason="excluded_app")

    def test_show_reads_like_a_diary(self):
        s = out(trail_cli.show, self.store, 40, True)
        for want in ("→ chat: Mum (WhatsApp)", "box+selected 0.95", "text +2 -0 (ax)", "+ hi", "typing x5 over 900 ms",
                     "click left AXButton “Send”", "gap: excluded_app"):
            self.assertIn(want, s)

    def test_places_lists_visits_with_duration(self):
        s = out(trail_cli.places, self.store, 1.0)
        self.assertIn("Mum", s)
        self.assertIn("chat", s)

    def test_forget_requires_a_choice(self):
        with self.assertRaises(SystemExit):
            trail_cli.forget(self.store, [])
        self.assertIn("removed 6", out(trail_cli.forget, self.store, ["--all"]))
        self.assertEqual(self.store.read(), [])

    def test_pause_flag(self):
        with config.use_paths(self.tmp.name):
            out(trail_cli.set_pause, True)
            self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "trail", ".paused")))
            out(trail_cli.set_pause, False)
            self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "trail", ".paused")))

    def test_status_without_a_file(self):
        with config.use_paths(self.tmp.name):
            self.assertIn("not running", out(trail_cli.status))
            os.makedirs(os.path.join(self.tmp.name, "trail"), exist_ok=True)
            with open(os.path.join(self.tmp.name, "trail", ".status.json"), "w") as fh:
                json.dump({"pid": os.getpid(), "updated": datetime.now().timestamp(), "gap": None}, fh)
            self.assertIn("running", out(trail_cli.status))

    def test_probe_dump_hides_typed_text_and_passwords(self):
        win = Node("AXWindow", [Node("AXTextArea", Value="my private draft", PlaceholderValue="Message Mum"),
                                Node("AXTextField", Subrole="AXSecureTextField", Value="hunter2"),
                                text("Mum"), Node("AXRow", [text("x")], Selected=True)], Title="WhatsApp")
        dump = trail_cli.dump_tree(win)
        self.assertNotIn("my private draft", dump)
        self.assertNotIn("hunter2", dump)
        self.assertIn('placeholder="Message Mum"', dump)
        self.assertIn("SELECTED", dump)


    def test_probe_dump_skips_empty_wrappers_and_does_not_open_toolbars(self):
        win = Node("AXWindow", [Node("AXToolbar", [Node("AXButton", Title="Back")]),
                                Node("AXGroup", [Node("AXGroup", [Node("AXWebArea", [text("hi")], Title="Page")])])], Title="W")
        dump = trail_cli.dump_tree(win)
        self.assertIn("AXToolbar (not opened)", dump)
        self.assertNotIn("Back", dump)
        self.assertNotIn("AXGroup", dump)
        self.assertIn('AXWebArea title="Page"', dump)
        self.assertIn('AXStaticText value="hi"', dump)


class MacFilesCompile(unittest.TestCase):
    def test_macos_only_files_at_least_compile(self):
        for name in ("trail_mac.py", "trail_cli.py"):
            py_compile.compile(os.path.join(os.path.dirname(__file__), "..", "src", name), doraise=True)


if __name__ == "__main__":
    unittest.main()
