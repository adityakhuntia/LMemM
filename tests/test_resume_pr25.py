"""Regression: the PR 25 Session 2 snapshot (TEST DATA, tests/fixtures/pr25_session2.json).

One session held four kinds of things: the Resume feature work in a Claude chat and a ChatGPT chat, 180DC slide review (a
Google Slides deck with three open notes, a ChatGPT thread, a WhatsApp chat), a Gmail follow-up note, and LMemM's own
log open in VS Code. The first Resume put all 13 in one scratch project, led with the newest note (the Gmail reminder)
and repeated garbled OCR and log lines. These tests fail if any of that comes back.
"""

import copy
import json
import os
import time
import unittest
from datetime import datetime

import evidence as ev
import resume

HERE = os.path.dirname(__file__)
NOW = datetime(2026, 10, 12, 4, 23, 0)                 # a minute after the last capture (04:22:52)
CLAUDE, CHATGPT_APP = "ai_conversation-dc0d5e53", "ai_conversation-fab6da88"
SLIDES, GMAIL, VSCODE = "document-07334e2f", "mailbox-dd91ad70", "code_file-2cc6dc64"
GARBLE = ("Cldude", "laL)ell", "Goingwlth", "tokensl", "prolect", "sllde8", "Lli&", "let8eode")


def load_doc():
    with open(os.path.join(HERE, "fixtures", "pr25_session2.json")) as fh:
        return json.load(fh)


def load():
    return {i["id"]: i for i in load_doc()["items"]}


def setUpModule():
    global _tz
    _tz = os.environ.get("TZ")
    os.environ["TZ"] = "Asia/Kolkata"                 # the machine the snapshot came from; the trail is in UTC
    time.tzset()


def tearDownModule():
    if _tz is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = _tz
    time.tzset()


def ids_in(b):
    claims = [c for s in b["sections"] for c in s["claims"]] + ([b["next"]] if b["next"] else [])
    return {c["source"]["item"] for c in claims}


class Pr25(unittest.TestCase):
    def setUp(self):
        self.items = load()
        self.before = copy.deepcopy(self.items)
        self.trail = load_doc()["trail"]
        self.b = resume.brief_scope(self.items, "PR 25", NOW, {}, events=self.trail)

    def tearDown(self):
        self.assertEqual(self.items, self.before, "Resume must not change the memory it reads")

    def test_thirteen_items_are_not_one_work_thread(self):
        groups = ev.threads([i for i in self.items.values() if not ev.self_made(i)])
        self.assertEqual(len(self.items), 13)
        self.assertGreaterEqual(len(groups), 7)
        self.assertLessEqual(max(len(g["items"]) for g in groups), 3)

    def test_brief_is_the_pr25_thread_only(self):
        self.assertEqual(self.b["state"], "rich")
        self.assertEqual(self.b["project_link"], "unconfirmed")
        self.assertEqual(self.b["title"], "PR 25")
        self.assertEqual({s["item"] for s in self.b["sources"]}, {CLAUDE})
        self.assertLessEqual(ids_in(self.b), {CLAUDE})

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

    def test_log_does_not_bridge_the_threads(self):
        self.assertTrue(ev.self_made(self.items[VSCODE]))
        merged = ev.threads([i for i in self.items.values() if not ev.self_made(i)])
        self.assertFalse(any({CLAUDE, SLIDES} <= {m["id"] for m in g["items"]} for g in merged))

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
        self.assertIn("does not establish", self.b["confidence"])
        low = resume.as_text(self.b).lower()
        for claim in ("tested", "merged", "deployed", "completed", "you decided", "see what it finished"):
            self.assertNotIn(claim, low)

    def test_your_own_words_identify_the_work(self):
        asked = next(s for s in self.b["sections"] if s["id"] == "asked")
        texts = [c["text"] for c in asked["claims"]]
        self.assertTrue(all(c["kind"] == "authored" and c["label"] == "You wrote this" for c in asked["claims"]))
        self.assertTrue(any("run a sample tets for me on this feature you have built" in t for t in texts))
        self.assertTrue(any("take the memory file for Session 2 of PR25" in t for t in texts))
        self.assertTrue(any("yup lets go with the apple style. lets code this up." in t for t in texts))
        self.assertEqual(self.b["relation"], "You typed in 2 Claude chats in your “memModel” project, all within this session.")

    def test_next_step_comes_from_the_strongest_open_request_not_the_newest(self):
        n = self.b["next"]
        self.assertIn("lets code this up", n["text"])
        self.assertIn("apple style", n["text"])
        self.assertIn("what you wrote earlier", n["text"])
        self.assertNotIn("Session 2", n["text"])               # the newer question is not the lead
        self.assertEqual(n["source"]["item"], CLAUDE)
        earlier = next(s for s in self.b["sections"] if s["id"] == "earlier")
        joined = " ".join(c["text"] for c in earlier["claims"])
        self.assertIn("clicking on back takes me to all projects", joined)
        self.assertIn("Apple's design principles", joined)

    def test_shared_words_are_not_shown_to_the_customer(self):
        text = resume.as_text(self.b)
        self.assertNotIn("Words that appear", text)
        self.assertNotIn("address, everything", text)
        self.assertNotIn("shared", text.lower())
        self.assertNotIn("shared", [k for k in self.b if k == "shared"] and "shared" or "")
        self.assertIn("covers similar ground, but I can't tell whether it is part of this work", text)
        self.assertEqual([m["item"] for m in self.b["maybe"]], [CHATGPT_APP])

    def test_without_the_trail_it_says_it_cannot_tell(self):
        b = resume.brief_scope(self.items, "PR 25", NOW, {})
        self.assertIsNone(b["next"])
        self.assertIn("can't reliably tell what you planned to do next", b["no_next"])
        text = resume.as_text(b)
        self.assertNotIn("see what it finished", text)
        self.assertIn("running a command", text)                 # still shown, as something seen, not as a plan

    def test_sources_open(self):
        for s in self.b["sources"]:
            self.assertTrue(s["can_open"])
        self.assertEqual(self.b["next"]["source"]["item"], CLAUDE)

    def test_matched_names_the_evidence(self):
        self.assertEqual([m["item"] for m in self.b["matched"]], [CLAUDE])


class Messages(unittest.TestCase):
    def test_messages_are_rebuilt_whole_with_typos_fixed(self):
        msgs = ev.authored_messages(load_doc()["trail"], load(), NOW)
        texts = [m["text"] for m in msgs]
        self.assertIn("run a sample tets for me on this feature you have built…", texts)
        self.assertFalse(any("ts run a sample" in t or "yuo yup" in t for t in texts))
        self.assertEqual(len({m["chat"] for m in msgs}), 2)
        self.assertEqual({m["item"] for m in msgs}, {CLAUDE})

    def test_nothing_after_now_is_used(self):
        msgs = ev.authored_messages(load_doc()["trail"], load(), datetime(2026, 10, 12, 4, 10, 0))
        self.assertTrue(msgs and all(m["at"] <= "2026-10-12T04:10:00" for m in msgs))
        self.assertFalse(any("lets code this up" in m["text"] for m in msgs))


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
        n = b["next"]
        if n:
            self.assertNotEqual(n["source"]["item"], GMAIL)
            self.assertNotEqual(n["kind"], "authored")


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
