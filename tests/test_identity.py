"""Stable document identity must survive missing OCR text and capture restarts."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import config
import identity
import resolver
import store as memstore
import tracker
import understand
from test_content import observation


DOC_ID = "abcdefghijklmnopqrstuv"
OLD_TEXT = "We chose SQLite because the data stays local."


def document(text="A different section of the document", title="Project plan", doc_id=DOC_ID):
    res, meta = observation(text, app="Safari", window=title, tab_title=title,
                            url=f"https://docs.google.com/document/d/{doc_id}/edit")
    return res, meta, understand.describe(res, meta)


def existing_item(st):
    ref = understand.ref(st)
    return {"id": "existing-document", "app": st["app"], "kind": st["kind"],
            "ref": ref, "refs": [ref], "last_seen": "2026-10-04T09:00:00",
            "activity": {c: {"seconds": 0, "text": [OLD_TEXT] if c == "typing" else []}
                         for c in memstore.CATEGORIES}, "typing_area": [250, 500, 450, 30]}


class DocumentIdentityTests(unittest.TestCase):
    def test_stable_doc_survives_restart_scroll_edit_and_rename(self):
        _, _, original = document()
        item = existing_item(original)
        items = {item["id"]: item}
        for trigger, scrolled, title, text in [
            ("start", False, "Project plan", "A different section of the document"),
            ("timer", False, "Project plan", "Completely revised document contents"),
            ("timer", True, "Project plan", "Another paragraph after scrolling"),
            ("start", False, "Renamed plan", "A new heading after renaming"),
        ]:
            with self.subTest(trigger=trigger, scrolled=scrolled, title=title):
                res, _, st = document(text, title)
                iid, _ = identity.resolve_item(items, st, None, res, trigger, scrolled)
                self.assertEqual(iid, "existing-document")

    def test_different_doc_ids_with_same_title_stay_separate(self):
        res, _, st = document(OLD_TEXT)
        item = existing_item(st)
        items = {item["id"]: item}
        _, _, other = document(OLD_TEXT, doc_id="differentdocumentidentifier")
        iid, _ = identity.resolve_item(items, other, {"item": item["id"]}, res, "timer", False)
        self.assertNotEqual(iid, item["id"])
        self.assertEqual(item["refs"], ["Google Docs|document|abcdefghijklmnopqrstuv"])

    def test_title_only_document_can_still_split_when_prior_typing_disappears(self):
        res, meta, _ = document()
        meta["url"] = "https://docs.google.com/document/"
        st = understand.describe(res, meta)
        item = existing_item(st)
        items = {item["id"]: item}
        iid, _ = identity.resolve_item(items, st, None, res, "start", False)
        self.assertNotEqual(iid, item["id"])

    def test_reused_email_draft_slot_can_still_create_a_new_draft(self):
        res, _, _ = document()
        st = {"app": "Gmail", "kind": "email_draft", "target": "compose"}
        item = existing_item(st)
        items = {item["id"]: item}
        iid, _ = identity.resolve_item(items, st, None, res, "timer", False)
        self.assertNotEqual(iid, item["id"])

    def test_only_verified_google_document_urls_bypass_content_splitting(self):
        res, meta, _ = document()
        for url, stable in [
            (f"https://docs.google.com/document/u/0/d/{DOC_ID}/edit", True),
            (f"https://example.com/document/d/{DOC_ID}/edit", False),
            (f"https://docs.google.com.evil.example/document/d/{DOC_ID}/edit", False),
            ("https://docs.google.com/document/d/new/edit", False),
            (f"https://docs.google.com/document/search/d/{DOC_ID}/edit", False),
        ]:
            with self.subTest(url=url):
                st = understand.describe(res, dict(meta, url=url))
                item = existing_item(st)
                items = {item["id"]: item}
                iid, _ = identity.resolve_item(items, st, None, res, "start", False)
                self.assertEqual(iid == item["id"], stable)

    def test_restart_preserves_content_and_links_two_sessions_to_one_document(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory)
            mem = Path(stack.enter_context(config.use_paths(directory)).memory_dir)
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))

            def process(capture, ts, text, title="Project plan"):
                res, meta, _ = document(text, title)
                meta.update(ts=ts, image=ts + ".jpg", iso=f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}T09:00:00")
                path = root / (ts + ".json")
                path.write_text(json.dumps(meta))
                Image.new("RGB", (1000, 800), "white").save(root / meta["image"])
                # OCR is controlled; identity, content, persistence and timelines are real.
                with patch.object(resolver, "resolve", return_value=res):
                    capture.handle(str(path), meta, "start", False)

            first = tracker.Tracker()
            first.session = "first-session"
            process(first, "20261004-090000", OLD_TEXT)
            iid = next(iter(first.items))
            first.items[iid]["activity"]["typing"]["text"] = [OLD_TEXT]
            first.items[iid]["typing_area"] = [250, 500, 450, 30]
            first.save()
            second = tracker.Tracker()
            second.session = "second-session"
            process(second, "20261005-090000", "Next step: test the migration.", "Renamed plan")
            items = memstore.load_items()
            self.assertEqual(list(items), [iid])
            self.assertEqual(items[iid]["visits"], 2)
            self.assertEqual(items[iid]["first_seen"], "2026-10-04T09:00:00")
            self.assertEqual(items[iid]["last_seen"], "2026-10-05T09:00:00")
            self.assertEqual(items[iid]["title"], "Renamed plan")
            self.assertEqual([e["text"] for e in items[iid]["content"]["excerpts"]],
                             [OLD_TEXT, "Next step: test the migration."])
            for session in ("first-session", "second-session"):
                saved = json.loads((mem / "sessions" / (session + ".json")).read_text())
                self.assertEqual([e["item"] for e in saved["timeline"]], [iid])


if __name__ == "__main__":
    unittest.main()
