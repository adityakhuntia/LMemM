"""context.py: a clean export for an AI - only notes and real content, nothing operational."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
import context
import lmemm
import notes
import store


def excerpt(text, at="2026-10-06T23:51:12", app="Brave Browser", url=None):
    return {"id": "x", "text": text, "source": {"app": app, "window": None, "url": url},
           "first_seen": at, "last_seen": at, "decision_quotes": []}


def thing(iid, app="Google Docs", kind="document", title="Q3 plan", excerpts=(), note_texts=(),
         state=None, visits=1, first="2026-10-06T23:49:00", last="2026-10-06T23:51:00"):
    i = {"id": iid, "app": app, "kind": kind, "title": title, "doing": f"Working on \"{title}\"",
        "state": state or {}, "mostly": "reading", "activity": {}, "first_seen": first, "last_seen": last,
        "seconds": 10, "visits": visits, "screenshot": iid + ".jpg",
        "notes": [{"at": f"2026-10-06T23:5{n}:00", "text": t, "while": "x"} for n, t in enumerate(note_texts)]}
    if excerpts:
        i["content"] = {"version": 1, "excerpts": list(excerpts)}
    return i


class CleaningTests(unittest.TestCase):
    def test_menu_bar_chrome_is_dropped_but_real_content_on_the_same_excerpt_survives(self):
        text = "Untitled document - Remind me to add project pricing document in this\nFile Edit View Insert Format Tools"
        self.assertEqual(context._clean(text), "Untitled document - Remind me to add project pricing document in this")

    def test_an_excerpt_that_is_pure_chrome_vanishes(self):
        self.assertIsNone(context._clean("File Edit View Insert Format Tools"))
        self.assertIsNone(context._clean("Edit View Insert Format Tools Extensions Help"))

    def test_identical_excerpts_after_cleaning_are_not_repeated(self):
        i = thing("a", excerpts=[excerpt("Pricing section here.\nFile Edit View Insert Format Tools"),
                                  excerpt("Pricing section here.\nEdit View Insert Format Tools Extensions Help")])
        self.assertEqual(context._content(i), ["Pricing section here."])


class DistillTests(unittest.TestCase):
    def test_a_thing_with_neither_a_note_nor_content_is_dropped(self):
        self.assertIsNone(context.distill(thing("a", note_texts=(), excerpts=())))

    def test_notes_carry_their_done_status(self):
        i = thing("a", note_texts=["add a pricing table", "ask Rahul"])
        notes.set_done({"a": i}, [notes.note_id(i["notes"][0])])
        row = context.distill(i)
        self.assertEqual(row["notes"], [{"text": "add a pricing table", "status": "done"},
                                        {"text": "ask Rahul", "status": "open"}])

    def test_no_operational_fields_leak_through(self):
        i = thing("a", note_texts=["x"], excerpts=[excerpt("hello")])
        row = context.distill(i)
        for leaked in ("id", "screenshot", "mostly", "activity", "seconds", "trigger", "ref", "content_hash"):
            self.assertNotIn(leaked, row)
        self.assertNotIn("content_hash", json.dumps(row))

    def test_when_summarises_the_span_without_per_visit_detail(self):
        row = context.distill(thing("a", note_texts=["x"], visits=7,
                                    first="2026-10-06T23:49:00", last="2026-10-06T23:51:00"))
        self.assertEqual(row["when"], "6 Oct, 23:49–23:51 (7 visits)")
        self.assertNotIn("visits", row)                                    # only inside the sentence

    def test_state_fields_that_duplicate_the_title_are_not_shown_twice(self):
        row = context.distill(thing("a", note_texts=["x"], state={"document": "Q3 plan", "owner": "me"}))
        self.assertEqual(row["details"], {"owner": "me"})


class GroupingTests(unittest.TestCase):
    def test_grouped_by_project_most_recent_first(self):
        items = {
            "a": thing("a", app="VS Code", kind="code_file", title="tracker.py",
                      state={"file": "tracker.py", "project": "LMemM"}, note_texts=["split it"],
                      last="2026-10-06T10:00:00"),
            "b": thing("b", title="Q3 plan", note_texts=["add pricing"], last="2026-10-06T12:00:00"),
            "c": thing("c", title="Empty doc", note_texts=(), excerpts=()),
        }
        projects = context.by_project(items)
        self.assertEqual([p["project"] for p in projects], ["Q3 plan", "LMemM"])
        self.assertEqual(sum(len(p["things"]) for p in projects), 2)       # the empty one is gone

    def test_for_session_only_includes_things_that_session_touched(self):
        items = {"a": thing("a", title="Q3 plan", note_texts=["x"]),
                 "b": thing("b", title="Other doc", note_texts=["y"])}
        doc = {"session": "s1", "timeline": [{"item": "a"}]}
        projects = context.for_session(items, doc)
        self.assertEqual([t["what"] for p in projects for t in p["things"]], ["Q3 plan"])

    def test_since_days_filters_by_last_seen(self):
        from datetime import datetime, timedelta
        now = datetime.now()
        items = {"recent": thing("recent", title="Fresh", note_texts=["x"],
                                 last=(now - timedelta(hours=2)).isoformat(timespec="seconds")),
                 "old": thing("old", title="Stale", note_texts=["y"],
                             last=(now - timedelta(days=10)).isoformat(timespec="seconds"))}
        projects = context.since(items, 1)
        self.assertEqual([t["what"] for p in projects for t in p["things"]], ["Fresh"])


class ExportAndCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.paths = self.stack.enter_context(config.use_paths(self.tmp.name))
        items = {"a": thing("a", title="Q3 plan", note_texts=["add pricing"], excerpts=[excerpt("Pricing here.")])}
        store.save_memory(items)
        store.save_session("s1", [{"from": "10:00", "to": "10:05", "seconds": 300, "item": "a", "app": "Google Docs",
                                   "doing": "Working on \"Q3 plan\"", "activity": {}, "trigger": "timer"}], [])

    def test_export_with_no_args_uses_the_latest_session_and_writes_a_file(self):
        doc, path = context.export()
        self.assertEqual(doc["session"], "s1")
        self.assertEqual(doc["things"], 1)
        self.assertEqual(doc["notes_open"], 1)
        self.assertTrue(path.exists())
        self.assertEqual(json.loads(path.read_text()), doc)

    def test_export_an_unknown_session_fails_clearly(self):
        with self.assertRaises(ValueError):
            context.export(session_id="missing")

    def test_cli_prints_the_document_and_a_summary_line(self):
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["lmemm.py", "context"]), contextlib.redirect_stdout(out), \
             contextlib.redirect_stderr(err):
            lmemm.main()
        self.assertEqual(json.loads(out.getvalue())["things"], 1)
        self.assertIn("1 things, 1 open notes", err.getvalue())

    def test_cli_days_and_session_are_mutually_exclusive(self):
        with patch("sys.argv", ["lmemm.py", "context", "s1", "--days", "1"]), self.assertRaises(SystemExit):
            lmemm.main()


if __name__ == "__main__":
    unittest.main()
