"""Notes as pending edits: ids, project view, done/reopen, resurfacing on reopen."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import config
import lmemm
import macos
import notes
import resolver
import store as memstore
import tracker
from input_store import InputStore
from test_content import observation
from test_dictation_integration import item as base_item


def item(iid, kind="document", title="Q3 plan", app="Google Docs", state=None, note_texts=()):
    i = base_item()
    i.update(id=iid, kind=kind, title=title, app=app, state=state or {})
    i["notes"] = [{"at": f"2026-10-06T10:0{n}:00", "text": t, "while": "x"} for n, t in enumerate(note_texts)]
    return i


class NoteModelTests(unittest.TestCase):
    def test_ids_are_stable_and_work_for_notes_written_before_ids(self):
        legacy = {"at": "2026-10-04T09:01:00", "text": "Next: test migration."}
        self.assertEqual(notes.note_id(legacy), notes.note_id(dict(legacy)))
        self.assertRegex(notes.note_id(legacy), r"^n-[0-9a-f]{6}$")
        self.assertNotEqual(notes.note_id(legacy), notes.note_id(dict(legacy, text="other")))

    def test_project_of(self):
        self.assertEqual(notes.project_of(item("a", kind="code_file", app="VS Code",
                                               state={"file": "x.py", "project": "LMemM"})), "LMemM")
        self.assertEqual(notes.project_of(item("b")), "Q3 plan")
        self.assertEqual(notes.project_of(item("c", kind="email_draft", app="Gmail")), "Email")
        self.assertEqual(notes.project_of(item("d", kind="chat", app="WhatsApp")), "Chats")
        self.assertEqual(notes.project_of(item("e", kind="web_page", app="GitHub")), "GitHub")

    def test_done_and_reopen_keep_notes_unchanged(self):
        a = item("a", note_texts=["add pricing", "ask Rahul"])
        items = {"a": a}
        before = json.dumps(a["notes"])
        first = notes.note_id(a["notes"][0])
        self.assertEqual(notes.set_done(items, [first, "n-missing"]), [first])
        self.assertEqual(json.dumps(a["notes"]), before)          # provenance matches notes by value
        self.assertEqual([n["text"] for n in notes.open_notes(a)], ["ask Rahul"])
        notes.set_done(items, [first], done=False)
        self.assertNotIn("notes_done", a)
        self.assertEqual(len(notes.open_notes(a)), 2)

    def test_project_view_groups_open_notes_and_hides_done(self):
        items = {"a": item("a", kind="code_file", app="VS Code", title="tracker.py",
                           state={"file": "tracker.py", "project": "LMemM"}, note_texts=["split tracker"]),
                 "b": item("b", kind="code_file", app="VS Code", title="store.py",
                           state={"file": "store.py", "project": "LMemM"}, note_texts=["atomic writes"]),
                 "c": item("c", note_texts=["add pricing"]),
                 "d": item("d", title="No notes here")}
        notes.set_done(items, [notes.note_id(items["c"]["notes"][0])])
        view = notes.pending_view(items)
        self.assertEqual(view["open"], 2)
        self.assertEqual([p["project"] for p in view["projects"]], ["LMemM"])
        self.assertEqual({e["what"] for e in view["projects"][0]["items"]}, {"tracker.py", "store.py"})
        everything = notes.pending_view(items, include_done=True)
        self.assertEqual({p["project"] for p in everything["projects"]}, {"LMemM", "Q3 plan"})
        self.assertIn("done", everything["projects"][-1]["items"][0]["notes"][0])

    def test_resurfacing_respects_open_notes_and_cooldown(self):
        a = item("a", note_texts=["add pricing"])
        self.assertEqual(len(notes.due_for_resurfacing(a, "2026-10-06T11:00:00", 600)), 1)
        a["resurfaced_at"] = "2026-10-06T10:55:00"
        self.assertEqual(notes.due_for_resurfacing(a, "2026-10-06T11:00:00", 600), [])
        a["notes"].append({"at": "2026-10-06T10:58:00", "text": "new since the last reminder"})
        self.assertEqual(len(notes.due_for_resurfacing(a, "2026-10-06T11:00:00", 600)), 2)
        a["notes"].pop()
        self.assertEqual(len(notes.due_for_resurfacing(a, "2026-10-06T11:06:00", 600)), 1)
        notes.set_done({"a": a}, [notes.note_id(a["notes"][0])])
        self.assertEqual(notes.due_for_resurfacing(a, "2026-10-06T12:00:00", 600), [])


class WidgetCardTests(unittest.TestCase):
    """notes.card: what the on-screen pill shows for the thing in front."""

    def setUp(self):
        self.items = {
            "here": item("here", kind="code_file", app="VS Code", title="tracker.py",
                         state={"file": "tracker.py", "project": "LMemM"}, note_texts=["split capture", "add tests"]),
            "there": item("there", kind="code_file", app="VS Code", title="store.py",
                          state={"file": "store.py", "project": "LMemM"}, note_texts=["atomic writes"]),
            "elsewhere": item("elsewhere", note_texts=["unrelated doc note"]),
        }
        notes.set_done(self.items, [notes.note_id(self.items["here"]["notes"][1])], at="2026-10-06T11:00:00")

    def test_left_shows_only_open_edits_of_the_project_with_this_thing_first(self):
        card = notes.card(self.items, "here")
        self.assertEqual(card["project"], "LMemM")
        self.assertEqual([n["text"] for n in card["left"]], ["split capture", "atomic writes"])
        self.assertEqual([n["here"] for n in card["left"]], [True, False])

    def test_plan_has_every_note_open_first_and_history_newest_first(self):
        card = notes.card(self.items, "here")
        self.assertEqual([(n["text"], bool(n["done"])) for n in card["plan"]],
                         [("split capture", False), ("atomic writes", False), ("add tests", True)])
        self.assertEqual(card["history"][0], {"at": "2026-10-06T11:00:00", "event": "done",
                                              "text": "add tests", "on": "tracker.py"})
        self.assertEqual(card["things"], 2)

    def test_ticking_in_the_card_leaves_only_what_is_left(self):
        card = notes.card(self.items, "here")
        notes.set_done(self.items, [card["left"][0]["id"]])
        self.assertEqual([n["text"] for n in notes.card(self.items, "here")["left"]], ["atomic writes"])
        self.assertIsNone(notes.card(self.items, "missing"))


class ResurfaceOnReopenTests(unittest.TestCase):
    """A note on A, a visit to B, back to A -> one reminder; back again soon -> none."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(config.use_paths(self.root))
        self.out = self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.notified = []
        self.stack.enter_context(patch.object(macos, "notify", side_effect=lambda *a: self.notified.append(a)))
        self.capture = tracker.Tracker()
        self.second = 0
        self.start = datetime(2026, 10, 6, 10, 0, 0)

    def note(self, ts, text):
        """Dictate a note right after frame `ts` (the tracker's clock pinned to then)."""
        at = datetime.strptime(ts, "%Y%m%d-%H%M%S") + timedelta(seconds=1)
        fixed = type("Clock", (datetime,), {"now": classmethod(lambda cls, tz=None: at)})
        with patch.object(tracker, "datetime", fixed):
            self.capture.save_note(("frame", ts), text)

    def visit(self, window, text):
        # frames on the real clock, a few seconds apart, so they line up with note times
        self.second += 5
        when = self.start + timedelta(seconds=self.second)
        ts, iso = when.strftime("%Y%m%d-%H%M%S"), when.isoformat(timespec="seconds")
        res, meta = observation(text, window=window, iso=iso)
        meta.update(ts=ts, image=ts + ".jpg", screen={"w": 1000, "h": 800})
        path = self.root / (ts + ".json")
        path.write_text(json.dumps(meta))
        Image.new("RGB", (1000, 800), "white" if window == "Q3 plan" else "gray").save(self.root / meta["image"])
        with patch.object(resolver, "resolve", return_value=res):
            self.capture.handle(str(path), meta, "app_switch", False)
        return ts

    def test_no_reminder_right_after_dictating_only_when_you_come_back(self):
        ts = self.visit("Q3 plan", "Pricing section goes here")
        self.note(ts, "add a pricing table")
        self.capture.close_interval()                         # the note window split the stretch
        self.visit("Q3 plan", "Pricing section goes here")   # still on the doc after saving
        self.visit("Q3 plan", "Pricing section goes here")
        self.assertEqual(self.notified, [])
        self.visit("Inbox", "Unrelated email list")
        self.visit("Q3 plan", "Pricing section goes here")   # now you came back
        self.assertEqual(len(self.notified), 1)

    def test_a_new_note_shows_next_time_even_inside_the_cooldown(self):
        ts = self.visit("Q3 plan", "Pricing section goes here")
        self.note(ts, "add a pricing table")
        self.visit("Inbox", "Unrelated email list")
        ts = self.visit("Q3 plan", "Pricing section goes here")
        self.assertEqual(len(self.notified), 1)
        self.note(ts, "and a comparison chart")
        self.visit("Inbox", "Unrelated email list")
        self.visit("Q3 plan", "Pricing section goes here")
        self.assertEqual(len(self.notified), 2)
        self.assertIn("comparison chart", self.notified[1][1])

    def test_note_resurfaces_once_when_you_come_back(self):
        ts = self.visit("Q3 plan", "Pricing section goes here")
        self.note(ts, "add a pricing table")
        self.assertEqual(self.notified, [])                   # not while you're writing it
        self.visit("Inbox", "Unrelated email list")
        self.visit("Q3 plan", "Pricing section goes here")
        self.assertEqual(len(self.notified), 1)
        self.assertIn("1 pending edit", self.notified[0][0])
        self.assertIn("add a pricing table", self.notified[0][1])
        self.visit("Inbox", "Unrelated email list")
        self.visit("Q3 plan", "Pricing section goes here")   # inside the cooldown
        self.assertEqual(len(self.notified), 1)
        timeline = json.loads(next(Path(config.paths().sessions_dir).glob("*.json")).read_text())["timeline"]
        self.assertEqual([bool(e.get("resurfaced")) for e in timeline], [False, False, True, False, False])
        pending = json.loads(Path(config.paths().pending_file).read_text())
        self.assertEqual(pending["open"], 1)
        self.assertEqual(pending["projects"][0]["items"][0]["notes"][0]["text"], "add a pricing table")

    def test_widget_card_follows_the_thing_in_front_and_ticks_save(self):
        ts = self.visit("Q3 plan", "Pricing section goes here")
        self.note(ts, "add a pricing table")
        card = self.capture.widget_card()
        self.assertEqual([n["text"] for n in card["left"]], ["add a pricing table"])
        self.capture.widget_tick([card["left"][0]["id"]], True)
        self.assertEqual(self.capture.widget_card()["left"], [])
        self.assertEqual(json.loads(Path(config.paths().pending_file).read_text())["open"], 0)

    def test_done_note_does_not_resurface(self):
        ts = self.visit("Q3 plan", "Pricing section goes here")
        self.note(ts, "add a pricing table")
        nid = notes.note_id(next(i for i in self.capture.items.values() if i.get("notes"))["notes"][0])
        self.capture.apply_control({"action": "notes_done", "ids": [nid], "done": True})
        self.visit("Inbox", "Unrelated email list")
        self.visit("Q3 plan", "Pricing section goes here")
        self.assertEqual(self.notified, [])
        public = json.loads(Path(config.paths().items_file).read_text())
        note = next(t for t in public["things"] if t.get("your_notes"))["your_notes"][0]
        self.assertEqual((note["id"], note["status"]), (nid, "done"))


class NotesCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.paths = self.stack.enter_context(config.use_paths(self.root))
        items = {"a": item("a", kind="code_file", app="VS Code", title="tracker.py",
                           state={"file": "tracker.py", "project": "LMemM"}, note_texts=["split tracker"]),
                 "b": item("b", note_texts=["add pricing"])}
        memstore.save_memory(items)
        self.nid = notes.note_id(items["a"]["notes"][0])

    def run_cli(self, *args):
        output = io.StringIO()
        with patch("sys.argv", ["lmemm.py", *args]), contextlib.redirect_stdout(output):
            lmemm.main()
        return output.getvalue()

    def test_project_view_and_filter(self):
        text = self.run_cli("notes")
        self.assertIn("2 pending edits", text)
        self.assertIn("LMemM  (1 open)", text)
        self.assertIn(self.nid, text)
        self.assertNotIn("pricing", self.run_cli("notes", "lmemm"))

    def test_done_while_stopped_writes_memory_directly(self):
        self.assertIn("1 note(s) marked done", self.run_cli("notes", "done", self.nid))
        self.assertNotIn("split tracker", self.run_cli("notes"))
        self.assertIn("split tracker", self.run_cli("notes", "--all"))
        self.run_cli("notes", "reopen", self.nid)
        self.assertIn("split tracker", self.run_cli("notes"))

    def test_done_while_running_goes_through_the_control_file(self):
        Path(self.paths.pidfile).write_text(str(os.getpid()))
        self.assertIn("sent to the running tracker", self.run_cli("notes", "done", self.nid))
        control = json.loads(Path(self.paths.control_file).read_text())
        self.assertEqual(control, {"pid": os.getpid(), "action": "notes_done", "ids": [self.nid], "done": True})
        self.assertIn("split tracker", self.run_cli("notes"))     # unchanged until the tracker applies it

    def test_done_while_stopped_keeps_provenance_consistent(self):
        memory_dir = Path(self.paths.memory_dir)
        items = memstore.load_items()
        evidence = InputStore("first", memory_dir)
        evidence.initialize_baseline(items)
        evidence.checkpoint(items, [], [])
        evidence.close()
        self.run_cli("notes", "done", self.nid)
        from input_store import plan_session_deletion
        plan = plan_session_deletion("first", {"data_dir": self.root, "memory_dir": memory_dir,
                                               "pidfile": self.paths.pidfile})
        self.assertFalse([b for b in plan["blockers"] if "outside recorded provenance" in b], plan["blockers"])
        rebuilt = plan["items"]["a"]
        self.assertIn(self.nid, rebuilt.get("notes_done", {}))
        self.assertEqual(len(rebuilt["notes"]), 1)


if __name__ == "__main__":
    unittest.main()
