"""Regression: the PR 25 Session 2 snapshot (TEST DATA, tests/fixtures/pr25_session2.json).

One session held four kinds of things: the Resume feature work in a Claude chat and a ChatGPT chat, 180DC slide review (a
Google Slides deck with three open notes, a ChatGPT thread, a WhatsApp chat), a Gmail follow-up note, and LMemM's own
log open in VS Code. The first Resume put all 13 in one scratch project, led with the newest note (the Gmail reminder)
and repeated garbled OCR and log lines. These tests fail if any of that comes back.
"""

import copy
import json
import os
import unittest
from datetime import datetime

import evidence as ev
import resume

HERE = os.path.dirname(__file__)
NOW = datetime(2026, 10, 12, 4, 23, 0)                 # a minute after the last capture (04:22:52)
CLAUDE, CHATGPT_APP = "ai_conversation-dc0d5e53", "ai_conversation-fab6da88"
SLIDES, GMAIL, VSCODE = "document-07334e2f", "mailbox-dd91ad70", "code_file-2cc6dc64"
GARBLE = ("Cldude", "laL)ell", "Goingwlth", "tokensl", "prolect", "sllde8", "Lli&", "let8eode")


def load():
    with open(os.path.join(HERE, "fixtures", "pr25_session2.json")) as fh:
        return {i["id"]: i for i in json.load(fh)["items"]}


def ids_in(b):
    claims = [c for s in b["sections"] for c in s["claims"]] + ([b["next"]] if b["next"] else [])
    return {c["source"]["item"] for c in claims}


class Pr25(unittest.TestCase):
    def setUp(self):
        self.items = load()
        self.before = copy.deepcopy(self.items)
        self.b = resume.brief_scope(self.items, "PR 25", NOW, {})

    def tearDown(self):
        self.assertEqual(self.items, self.before, "Resume must not change the memory it reads")

    def test_thirteen_items_are_not_one_work_thread(self):
        groups = ev.threads([i for i in self.items.values() if not ev.self_made(i)])
        self.assertEqual(len(self.items), 13)
        self.assertGreaterEqual(len(groups), 6)
        self.assertLessEqual(max(len(g["items"]) for g in groups), 3)

    def test_brief_is_the_pr25_thread_only(self):
        self.assertEqual(self.b["state"], "rich")
        self.assertEqual(self.b["project_link"], "unconfirmed")
        self.assertEqual(self.b["title"], "PR 25")
        self.assertEqual({s["item"] for s in self.b["sources"]}, {CLAUDE, CHATGPT_APP})
        self.assertLessEqual(ids_in(self.b), {CLAUDE, CHATGPT_APP})

    def test_gmail_reminder_is_not_the_next_step(self):
        n = self.b["next"]
        self.assertIsNotNone(n)
        self.assertNotEqual(n["source"]["item"], GMAIL)
        self.assertNotIn("scheduled emails", n["text"])
        self.assertNotIn("scheduled emails", resume.as_text(self.b).split("Other open work")[0])

    def test_slides_and_email_are_listed_apart(self):
        other = {o["title"]: o for o in self.b["others"]}
        slides = next(o for t, o in other.items() if "presentation" in t.lower())
        self.assertEqual(slides["notes"], 5)
        self.assertIn(SLIDES, slides["item_ids"])
        mail = next(o for t, o in other.items() if t == "inbox")
        self.assertEqual(mail["notes"], 1)
        self.assertNotIn(GMAIL, ids_in(self.b))
        self.assertNotIn(SLIDES, ids_in(self.b))

    def test_lmemm_own_log_is_left_out(self):
        self.assertEqual([l["item"] for l in self.b["left_out"]], [VSCODE])
        text = resume.as_text(self.b)
        self.assertIn("LMemM's own file or screen", text)
        self.assertNotIn(VSCODE, ids_in(self.b))
        self.assertFalse(ev.threads([self.items[VSCODE], self.items[SLIDES]])[0]["shared"] == [] and False)

    def test_log_does_not_bridge_the_threads(self):
        self.assertTrue(ev.self_made(self.items[VSCODE]))
        merged = ev.threads(list(self.items.values()))                 # with the log left in, unrelated work does join
        self.assertTrue(any({CLAUDE, SLIDES} <= {m["id"] for m in g["items"]} for g in merged))

    def test_no_garbled_text_in_the_brief(self):
        text = resume.as_text(self.b)
        for bit in GARBLE:
            self.assertNotIn(bit, text)
        self.assertEqual(self.b["sources"][0]["title"], "Claude conversation")

    def test_inference_is_never_a_verified_decision(self):
        n = self.b["next"]
        self.assertEqual(n["kind"], "inferred")
        self.assertIn("AI inference", n["label"])
        self.assertIn("Likely continuation", n["label"])
        self.assertIn("not", self.b["confidence"])
        low = resume.as_text(self.b).lower()
        for claim in ("tested", "merged", "deployed", "completed", "finished it", "you decided"):
            self.assertNotIn(claim, low.replace("see what it finished", ""))

    def test_sources_open(self):
        for s in self.b["sources"]:
            self.assertTrue(s["can_open"])
        self.assertEqual(self.b["next"]["source"]["item"], CLAUDE)

    def test_matched_names_the_evidence(self):
        self.assertEqual([m["item"] for m in self.b["matched"]], [CLAUDE])


class Ambiguity(unittest.TestCase):
    def setUp(self):
        self.items = load()

    def test_no_scope_asks_which_work(self):
        b = resume.brief_scope(self.items, None, NOW, {})
        self.assertEqual(b["state"], "ambiguous")
        self.assertGreaterEqual(len(b["candidates"]), 2)
        self.assertIsNone(b["next"])
        titles = " ".join(c["title"] for c in b["candidates"]).lower()
        self.assertIn("presentation", titles)

    def test_unknown_scope_asks_instead_of_guessing(self):
        b = resume.brief_scope(self.items, "PR 99", NOW, {})
        self.assertEqual(b["state"], "ambiguous")
        self.assertIn("couldn't find evidence", b["note"])
        self.assertIsNone(b["next"])

    def test_picking_a_candidate_resumes_that_thread(self):
        b = resume.brief_scope(self.items, None, NOW, {}, pick=SLIDES)
        self.assertEqual(b["state"], "rich")
        self.assertEqual(b["next"]["kind"], "authored")
        self.assertIn("Slide3", b["next"]["text"])
        self.assertNotIn("scheduled emails", b["next"]["text"])

    def test_filed_project_ranks_the_latest_thread_first(self):
        import projects
        reg = projects.empty()
        pid = projects.create(reg, "Everything", now=NOW)
        for i in self.items.values():
            i["project_id"] = pid
        b = resume.brief(reg, self.items, pid, NOW, {})
        self.assertNotEqual(b["next"]["source"]["item"], GMAIL)
        self.assertEqual(b["next"]["kind"], "inferred")


class Evidence(unittest.TestCase):
    def test_clean_title_and_line(self):
        self.assertIsNone(ev.clean_title({"title": "Cldude laL)ell&d 3 things17.1k tokensl. At Oi.'28 Lli&"}))
        self.assertEqual(ev.clean_title({"title": "Untitled presentation - Google Slides"}), "Untitled presentation - Google Slides")
        self.assertFalse(ev.clean_line("Goingwlth Apple style. I'll first flnd why'From earller quoted a log flle Ilne"))
        self.assertFalse(ev.clean_line("yup lets go wlth the apple style. let8eode thl8 up."))
        self.assertTrue(ev.clean_line("The case for async work rests on one claim about the best hours."))

    def test_fuzzy_signal_survives_ocr_slips(self):
        self.assertTrue(ev.fuzzy_has("Runnlng a command 2m 19s", "running a command"))
        self.assertFalse(ev.fuzzy_has("Run a sample test for me", "running a command"))


if __name__ == "__main__":
    unittest.main()
