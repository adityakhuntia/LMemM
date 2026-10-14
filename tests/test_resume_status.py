"""Resume: what became of a request, the honest next step, and your corrections (evidence.py R33, resume_feedback.py R34).

The PR 25 cases use tests/fixtures/pr25_session2.json (TEST DATA) read through the same loader as test_resume_pr25.
"""

import copy
import hashlib
import json
import os
import tempfile
import time
import unittest
from datetime import datetime

import evidence as ev
import projects
import resume
import resume_cli
import resume_demo
import resume_feedback as rf
import source_ref
import test_resume_pr25 as pr25

setUpModule, tearDownModule = pr25.setUpModule, pr25.tearDownModule
NOW = pr25.NOW


def msg(text, at, chat="aaaa1111", item="i1"):
    return {"text": text, "at": at, "chat": chat, "item": item, "project": None}


ITEM_WORKING = {"id": "i1", "content": {"excerpts": [{"text": "Running a command", "last_seen": "2026-10-12T04:22:00"}]}}


class Status(unittest.TestCase):
    def test_unknown_is_not_open_and_a_reply_is_not_completion(self):
        r = msg("please build the settings page", "2026-10-12T04:00:00")
        s = ev.request_status(r, [r], {"id": "i1"}, True)
        self.assertEqual(s["status"], "unknown")

    def test_working_after_the_request_is_only_likely_addressed(self):
        r = msg("please build the settings page", "2026-10-12T04:00:00")
        s = ev.request_status(r, [r], ITEM_WORKING, True)
        self.assertEqual(s["status"], "likely_addressed")
        self.assertIn("does not show it was finished", s["why"])

    def test_working_before_the_request_proves_nothing(self):
        r = msg("please build the settings page", "2026-10-12T04:30:00")
        self.assertEqual(ev.request_status(r, [r], ITEM_WORKING, True)["status"], "unknown")

    def test_a_signal_from_a_window_with_two_chats_is_not_attributed(self):
        r = msg("please build the settings page", "2026-10-12T04:00:00")
        self.assertEqual(ev.request_status(r, [r], ITEM_WORKING, False)["status"], "unknown")

    def test_open_only_when_you_chased_it(self):
        r = msg("please build the settings page", "2026-10-12T04:00:00")
        later = msg("it still doesn't work, nothing happened", "2026-10-12T04:05:00")
        self.assertEqual(ev.request_status(r, [r, later], {"id": "i1"}, True)["status"], "open")

    def test_completed_only_when_you_said_so(self):
        r = msg("please build the settings page", "2026-10-12T04:00:00")
        later = msg("that worked, thanks", "2026-10-12T04:05:00")
        self.assertEqual(ev.request_status(r, [r, later], ITEM_WORKING, True)["status"], "completed")


class Pr25(unittest.TestCase):
    def setUp(self):
        self.doc = pr25.load_doc()
        self.items = {i["id"]: i for i in self.doc["items"]}
        self.trail = self.doc["trail"]
        self.before = json.dumps(self.doc, sort_keys=True)

    def scoped(self, **kw):
        return resume.brief_scope(self.items, "PR 25", NOW, {}, None, self.trail, **kw)

    def filed(self, **kw):
        reg = projects.empty()
        pid = projects.create(reg, "Everything", now=NOW)
        for i in self.items.values():
            i["project_id"] = pid
        return resume.brief(reg, self.items, pid, NOW, {}, events=self.trail, **kw)

    def test_the_request_is_a_check_not_a_task_and_never_mac(self):
        b = self.scoped()
        text = resume.as_text(b)
        self.assertIn("check where it got to", b["next"]["text"])
        self.assertEqual(b["request"]["status"], "unknown")
        for bit in ("mac", "test it", "push", "merged", "finished it", "see what it finished"):
            self.assertNotIn(bit, b["next"]["text"].lower())
        self.assertIn("What Resume cannot determine", text)
        self.assertTrue(b["next"]["source"]["can_open"])

    def test_the_top_is_one_sentence_and_one_action(self):
        for b in (self.scoped(), self.filed()):
            top = b["top"]
            self.assertTrue(top["headline"].startswith("You asked Claude: “lets go with the apple style. lets code this up”."))
            # the Claude chat has no saved address: say so, lead with what LMemM saved, and never imply the app finds the chat
            self.assertIn("I can't tell from this capture whether it finished. LMemM didn't save an address for that chat, so it can't take you to it.", top["headline"])
            self.assertEqual((top["action"]["label"], top["action"]["mode"], top["action"]["item"]), ("Show in LMemM", "lmemm", pr25.CLAUDE))
            self.assertEqual(top["action"]["also"]["label"], "Open Claude")
            self.assertIn("starts the app only", top["action"]["note"])
            for bit in ("mac", "push", "test it", "merged", "is still open", "unfinished"):
                self.assertNotIn(bit, top["headline"].lower())
            text = resume.as_text(b)
            self.assertLess(text.index(top["headline"]), text.index("## Why"))
            self.assertLess(text.index("Action: Show in LMemM"), text.index("## Why"))

    def test_a_chat_with_an_address_opens_the_conversation(self):
        items = copy.deepcopy(self.items)
        for e in items[pr25.CLAUDE]["content"]["excerpts"]:
            e["source"]["url"] = "https://claude.ai/chat/abc"
        b = resume.brief_scope(items, "PR 25", NOW, {}, None, self.trail)
        self.assertEqual((b["top"]["action"]["label"], b["top"]["action"]["mode"]), ("Open conversation", "source"))
        self.assertIsNone(b["top"]["action"]["note"])
        self.assertIn("Open the conversation to check.", b["top"]["headline"])

    def test_why_keeps_what_you_wrote_apart_from_what_the_app_saw_and_what_was_inferred(self):
        text = resume.as_text(self.scoped())
        order = [text.index(h) for h in ("**What you wrote**", "**What the app observed**", "**What Resume inferred**", "**What Resume cannot determine**")]
        self.assertEqual(order, sorted(order))
        wrote = text[order[0]:order[1]]
        self.assertNotIn("running a command", wrote)
        self.assertTrue(all("You wrote this" in l for l in wrote.splitlines()[1:] if l.startswith("- ")))
        self.assertIn("(in your other chat)", wrote)                           # typed messages are matched to their chat

    def test_only_the_screen_observation_is_called_unassignable(self):
        b = self.scoped()
        gaps = " ".join(b["cant_tell"])
        self.assertIn("which chat the “running a command” screen belongs to", gaps)
        self.assertIn("your typed messages are matched to their chats from the event trail", gaps)
        self.assertNotIn("running a command", b["top"]["headline"])
        self.assertNotIn("screen", b["top"]["headline"])
        self.assertTrue(any(c["chat"] for c in next(s for s in b["sections"] if s["id"] == "asked")["claims"]))

    def test_cli_and_window_paths_agree(self):
        a, w = self.scoped(), self.filed()
        self.assertEqual(a["next"]["text"], w["next"]["text"])
        self.assertEqual(a["request"]["status"], w["request"]["status"])
        self.assertEqual(a["next"]["source"]["item"], w["next"]["source"]["item"])

    def test_unrelated_work_never_leads_either_path(self):
        for b in (self.scoped(), self.filed()):
            self.assertNotIn(pr25.GMAIL, b["next"]["source"]["item"])
            self.assertNotIn("Slide", b["next"]["text"])
            self.assertNotIn("labels_log", resume.as_text(b).split("Left out")[0])

    def test_every_claim_has_a_label_and_a_source(self):
        b = self.scoped()
        for s in b["sections"]:
            for c in s["claims"]:
                self.assertIn(c["label"].split(" ·")[0], ("You wrote this", "Seen on screen", "Observed", "AI inference", "From your note", "Seen, not confirmed"))
                self.assertTrue(c["source"]["item"])
        self.assertEqual(b["next"]["kind"], "inferred")

    def test_corrections_leave_the_evidence_alone(self):
        b = self.scoped()
        k = b["next"]["key"]
        fb = rf.record(rf.empty(), "outdated", step_key=k, at="2026-10-12T05:00:00")
        again = self.scoped(feedback=fb)
        self.assertNotEqual(again["next"] and again["next"]["key"], k)       # not offered again
        self.assertIn("pick up from there", resume.as_text(again) if not again["next"] else "pick up from there")
        mine = rf.record(rf.empty(), "replace", step_key=k, text="Review the Apple-style pill", at="2026-10-12T05:00:00")
        r = self.scoped(feedback=mine)
        self.assertEqual((r["next"]["text"], r["next"]["label"]), ("Review the Apple-style pill", "You wrote this"))
        yes = self.scoped(feedback=rf.record(rf.empty(), "right", step_key=k))
        self.assertTrue(yes["confirmed"])
        self.assertEqual(yes["next"]["text"], b["next"]["text"])
        self.assertEqual(json.dumps(self.doc, sort_keys=True), self.before)    # memory and trail untouched

    def test_excluding_a_source_leaves_it_out_but_remembers_it(self):
        b = self.scoped(feedback=rf.record(rf.empty(), "exclude", item_id=pr25.CLAUDE))
        self.assertEqual([e["item"] for e in b["excluded"]], [pr25.CLAUDE])
        self.assertNotIn(pr25.CLAUDE, pr25.ids_in(b))
        self.assertIn(pr25.CLAUDE, self.items)

    def test_cli_corrections_write_only_their_own_file(self):
        with tempfile.TemporaryDirectory() as d:
            mem, trail, fbf = (os.path.join(d, n) for n in ("memory.json", "trail.jsonl", "fb.json"))
            json.dump({"items": self.doc["items"]}, open(mem, "w"))
            with open(trail, "w") as fh:
                fh.write("\n".join(json.dumps(e) for e in self.trail))
            digest = hashlib.sha256(open(mem, "rb").read()).hexdigest()
            args = ["--scope", "PR 25", "--memory", mem, "--trail", trail, "--feedback", fbf, "--now", NOW.isoformat()]
            first = resume_cli.run(args)
            resume_cli.run(args + ["--mark", "outdated"])
            self.assertEqual(hashlib.sha256(open(mem, "rb").read()).hexdigest(), digest)
            self.assertEqual(len(json.load(open(fbf))["steps"]), 1)
            self.assertNotEqual((resume_cli.run(args)["next"] or {}).get("key"), first["next"]["key"])


class Explained(unittest.TestCase):
    def test_every_state_explains_its_recommendation(self):
        reg, items, book = resume_demo.build(NOW)
        for pid, p in reg["projects"].items():
            top = resume.brief(reg, items, pid, NOW, book)["top"]
            self.assertTrue(top["because"].strip(), p["name"])
            self.assertTrue(top["why_label"].startswith("Why ") and top["why_label"].endswith("?"))

    def test_pr25_explains_why_it_points_at_the_app_not_the_chat(self):
        doc = pr25.load_doc()
        b = resume.brief_scope({i["id"]: i for i in doc["items"]}, "PR 25", NOW, {}, None, doc["trail"])
        self.assertEqual(b["top"]["why_label"], "Why can't Resume open the chat?")
        self.assertIn("can't read Claude's replies", b["top"]["because"])
        self.assertIn("no address for that chat", b["top"]["because"])

    def test_the_demo_says_it_is_a_demo_not_that_setup_is_unfinished(self):
        import window_model
        banner = window_model.demo_banner()
        self.assertEqual((banner["tone"], banner["kind"]), ("calm", "demo"))
        self.assertIn("made-up", banner["line"])
        self.assertNotIn("Setup", banner["title"] + banner["line"])


class ExactSource(unittest.TestCase):
    """Reopening the exact page or file (source_ref.py R36-R39, resume.open_command)."""

    def demo(self, folder=None):
        reg, items, book = resume_demo.build(NOW, folder=folder)
        by = {p["name"]: pid for pid, p in reg["projects"].items()}
        return reg, items, book, by

    def test_1_a_safari_page_with_an_address_opens_that_exact_page(self):
        reg, items, book, by = self.demo()
        cmd = resume.open_command(items["k1"])
        self.assertEqual(cmd["args"], ["open", "-a", "Safari", "https://example.org/kitchen-cabinets"])
        self.assertTrue(cmd["exact"])
        top = resume.brief(reg, items, by["Kitchen reno (exact page)"], NOW, book)["top"]
        self.assertEqual((top["action"]["label"], top["action"]["mode"]), ("Open source", "source"))
        self.assertIsNone(top["action"]["note"])
        self.assertIn("Open source to pick up from there.", top["headline"])

    def test_2_safari_with_no_address_says_it_can_open_safari_but_not_the_page(self):
        reg, items, book, by = self.demo()
        cmd = resume.open_command(items["g1"])
        self.assertEqual((cmd["args"], cmd["exact"]), (["open", "-a", "Safari"], False))
        top = resume.brief(reg, items, by["Garage shelves"], NOW, book)["top"]
        self.assertIn("starts the app only; it can't take you to the page", top["action"]["note"])
        self.assertEqual(top["action"]["label"], "Show in LMemM")                # the saved title stays reachable

    def test_3_stale_or_invalid_references_fail_gracefully_and_keep_the_item(self):
        reg, items, book, by = self.demo(tempfile.mkdtemp())
        gone = resume.open_command(items["r1"])                                 # the file moved away
        self.assertEqual((gone["exact"], gone["args"]), (False, ["open", "-a", "Preview"]))
        self.assertIn("isn't at its saved location any more", gone["problem"])
        b = resume.brief(reg, items, by["Old receipts (file gone)"], NOW, book)
        self.assertIn("isn't at its saved location any more", b["top"]["headline"])
        self.assertEqual(b["top"]["action"]["mode"], "lmemm")
        self.assertIn("r1", items)
        bad = {"id": "x", "app": "Safari", "source": {"kind": "url", "value": "javascript:alert(1)"}}
        self.assertEqual(resume.open_command(bad)["exact"], False)
        self.assertIn("no longer a safe web address", resume.original_of(bad)["problem"])

    def test_4_a_local_file_opens_that_exact_file(self):
        folder = tempfile.mkdtemp()
        reg, items, book, by = self.demo(folder)
        resume_demo.seed(folder, NOW)                                           # writes Lease summary.txt
        cmd = resume.open_command(items["l1"])
        self.assertEqual((cmd["args"], cmd["exact"]), (["open", os.path.join(folder, "Lease summary.txt")], True))
        top = resume.brief(reg, items, by["Lease (local file)"], NOW, book)["top"]
        self.assertEqual((top["action"]["label"], top["action"]["mode"]), ("Open source", "source"))

    def test_5_skipped_private_and_excluded_sources_are_never_kept_or_exposed(self):
        for url in ("https://accounts.google.com/signin", "https://www.mybank.com/home", "https://x.org/?access_token=abc",
                    "https://user:pw@x.org/", "file:///etc/passwd", "http://", "https://x.org/a b"):
            self.assertIsNone(source_ref.clean_url(url), url)
        self.assertIsNone(source_ref.file_path("file:///Users/me/.ssh/id_rsa"))
        self.assertIsNone(source_ref.file_path("file:///Users/me/../root/x"))
        item = {}
        self.assertFalse(source_ref.remember(item, {"url": "https://accounts.google.com/x", "app": "Safari", "iso": "t"}))
        self.assertNotIn("source", item)
        reg, items, book, by = self.demo()
        b = resume.brief(reg, items, by["Kitchen reno (exact page)"], NOW, book, feedback=rf.record(rf.empty(), "exclude", item_id="k1"))
        self.assertEqual(b["state"], "empty")                                   # nothing left to reopen
        text = resume.as_text(resume.brief(reg, items, by["Kitchen reno (exact page)"], NOW, book))
        self.assertNotIn("example.org", text)                                    # the address is never printed or copied
        for name in ("ask", "labels", "memory_search", "brief", "recap", "suggestions", "tasks", "understand"):
            with open(os.path.join(os.path.dirname(__file__), "..", "src", name + ".py")) as fh:
                self.assertNotIn("source_ref", fh.read(), name)                  # nothing that talks to a model reads it

    def test_6_back_from_the_item_page_returns_to_the_same_resume_page(self):
        import page_model
        reg, items, book, by = self.demo()
        pid = by["Kitchen reno (exact page)"]
        st = page_model.press(reg, page_model.new_state(), "go", pid, items)
        st = page_model.press(reg, st, "resume", pid, items)
        st = page_model.press(reg, st, "thing", "k1", items)                     # Show in LMemM
        self.assertEqual(st["view"], "thing")
        st = page_model.press(reg, st, "back", None, items)
        self.assertEqual((st["view"], st["pid"]), ("resume", pid))

    def test_capture_keeps_the_newest_address_and_does_not_erase_it_on_a_frame_without_one(self):
        item = {}
        source_ref.remember(item, {"url": "https://example.org/a", "app": "Safari", "tab_title": "A", "iso": "2026-10-12T09:00:00"})
        source_ref.remember(item, {"url": "https://example.org/b", "app": "Safari", "tab_title": "B", "iso": "2026-10-12T09:05:00"})
        source_ref.remember(item, {"url": None, "app": "Safari", "iso": "2026-10-12T09:06:00"})
        self.assertEqual((item["source"]["value"], item["source"]["title"]), ("https://example.org/b", "B"))
        source_ref.remember(item, {"file": "file:///Users/me/Documents/lease%20summary.pdf", "app": "Preview", "iso": "2026-10-12T09:07:00"})
        self.assertEqual(item["source"]["value"], "/Users/me/Documents/lease summary.pdf")


class Sparse(unittest.TestCase):
    def test_garage_shelves_stays_limited_in_both_paths(self):
        reg, items, book = resume_demo.build(NOW)
        pid = next(p for p, v in reg["projects"].items() if v["name"] == "Garage shelves")
        for events in (None, [], pr25.load_doc()["trail"]):
            b = resume.brief(reg, items, pid, NOW, book, events=events)
            self.assertEqual(b["state"], "limited")
            self.assertIsNone(b["next"])
            self.assertIn("can't reliably tell what you planned to do next", b["no_next"])
            text = resume.as_text(b)
            self.assertIn("I found “Garage shelving ideas,” but I can't tell what you planned to do next, and LMemM has no saved address to reopen it.", text)
            self.assertNotIn("to find the page", text)                          # the app is never said to find the page
            self.assertIn("## Why can't Resume open the page?", text)
            self.assertIn("only recent source LMemM found", text)
            self.assertEqual((b["top"]["action"]["label"], b["top"]["action"]["mode"]), ("Show in LMemM", "lmemm"))
            self.assertEqual(b["top"]["action"]["also"]["label"], "Open Safari")
            self.assertIn("starts the app only; it can't take you to the page", b["top"]["action"]["note"])


if __name__ == "__main__":
    unittest.main()
