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
        self.assertIn("Resume cannot tell", text)
        self.assertTrue(b["next"]["source"]["can_open"])

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


class Sparse(unittest.TestCase):
    def test_garage_shelves_stays_limited_in_both_paths(self):
        reg, items, book = resume_demo.build(NOW)
        pid = next(p for p, v in reg["projects"].items() if v["name"] == "Garage shelves")
        for events in (None, [], pr25.load_doc()["trail"]):
            b = resume.brief(reg, items, pid, NOW, book, events=events)
            self.assertEqual(b["state"], "limited")
            self.assertIsNone(b["next"])
            self.assertIn("can't reliably tell what you planned to do next", b["no_next"])
            self.assertIn("Open the most recent source", resume.as_text(b))


if __name__ == "__main__":
    unittest.main()
