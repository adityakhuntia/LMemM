"""Resume this project (resume.py): every claim has a source and a kind, thin and old history say so, nothing is invented."""

import unittest
from datetime import datetime, timedelta

import page_model
import projects
import resume
import resume_demo

NOW = datetime(2026, 10, 11, 12, 0)


def ids():
    reg, items, book = resume_demo.build(NOW)
    return reg, items, book, {p["name"]: pid for pid, p in reg["projects"].items()}


def every_claim(b):
    return [c for s in b["sections"] for c in s["claims"]] + ([b["next"]] if b["next"] else [])


class Rich(unittest.TestCase):
    def setUp(self):
        reg, items, book, by = ids()
        self.b = resume.brief(reg, items, by["Remote work essay"], NOW, book)

    def test_state_and_sections(self):
        self.assertEqual(self.b["state"], "rich")
        titles = [s["title"] for s in self.b["sections"]]
        self.assertIn("Where things stand", titles)
        self.assertIn("Open question or blocker", titles)

    def test_every_claim_has_a_kind_label_and_source(self):
        claims = every_claim(self.b)
        self.assertGreaterEqual(len(claims), 5)
        for c in claims:
            self.assertIn(c["kind"], ("authored", "observed", "inferred"))
            self.assertTrue(c["label"])
            self.assertTrue(c["source"]["item"] and c["source"]["at"] and c["source"]["title"], c)

    def test_inference_is_labelled_and_only_from_the_task_book(self):
        inferred = [c for c in every_claim(self.b) if c["kind"] == "inferred"]
        self.assertEqual([c["label"] for c in inferred], ["AI inference"])

    def test_next_step_is_your_note_not_a_guess(self):
        self.assertEqual(self.b["next"]["kind"], "authored")
        self.assertIn("onboarding counter-argument", self.b["next"]["text"])

    def test_question_note_is_the_blocker_and_not_the_next_step(self):
        blocker = next(s for s in self.b["sections"] if s["id"] == "blocker")["claims"][0]
        self.assertIn("Stanford", blocker["text"])
        self.assertNotEqual(blocker["text"], self.b["next"]["text"])

    def test_decision_is_a_quote_not_a_fact(self):
        d = next(s for s in self.b["sections"] if s["id"] == "decisions")
        self.assertEqual(d["claims"][0]["label"], "Seen, not confirmed")
        self.assertFalse(d["conflict"])

    def test_away_and_text(self):
        self.assertTrue(self.b["away"])
        text = resume.as_text(self.b)
        self.assertIn("AI inference", text)
        self.assertIn("From your note", text)


class Honest(unittest.TestCase):
    def test_sparse_says_so_and_adds_nothing(self):
        reg, items, book, by = ids()
        b = resume.brief(reg, items, by["Garage shelves"], NOW, book)
        self.assertEqual(b["state"], "limited")
        self.assertIn("limited context", b["note"])
        self.assertEqual([s["id"] for s in b["sections"]], ["stand"])
        self.assertIsNone(b["next"])
        self.assertEqual(len(every_claim(b)), 1)

    def test_stale_says_so(self):
        reg, items, book, by = ids()
        b = resume.brief(reg, items, by["Tax 2024"], NOW, book)
        self.assertEqual(b["state"], "stale")
        self.assertIn("out of date", b["note"])
        self.assertIn("5 weeks", b["note"])

    def test_conflicting_decisions_are_shown_not_picked(self):
        reg, items, book, by = ids()
        b = resume.brief(reg, items, by["Pricing page"], NOW, book)
        d = next(s for s in b["sections"] if s["id"] == "decisions")
        self.assertTrue(d["conflict"])
        self.assertIn("may not agree", d["note"])
        self.assertEqual(len(d["claims"]), 2)
        self.assertEqual({c["source"]["item"] for c in d["claims"]}, {"p1", "p2"})
        self.assertIn("may not agree", resume.as_text(b))
        self.assertFalse([s for s in b["sections"] if s["id"] == "goal"])     # no task: no goal is invented

    def test_empty_project(self):
        reg, items, book, by = ids()
        pid = projects.create(reg, "Nothing yet")
        b = resume.brief(reg, items, pid, NOW, book)
        self.assertEqual(b["state"], "empty")
        self.assertEqual(b["sections"], [])

    def test_off_limits_things_never_appear(self):
        reg, items, book, by = ids()
        import config
        config.TASK_OFF_APPS.add("Slack")
        try:
            b = resume.brief(reg, items, by["Pricing page"], NOW, book)
        finally:
            config.TASK_OFF_APPS.discard("Slack")
        self.assertNotIn("p2", {c["source"]["item"] for c in every_claim(b)})

    def test_task_that_is_mostly_elsewhere_is_ignored(self):
        reg, items, book, by = ids()
        b = resume.brief(reg, items, by["Pricing page"], NOW, {"x": {"at": NOW.isoformat(), "tasks": [
            {"title": "T", "goal": "Other work", "items": ["e1", "p1", "e2"], "open": "Do it"}]}})
        self.assertEqual(b["used"]["tasks"], 0)


class Original(unittest.TestCase):
    def test_url_then_app_then_none(self):
        reg, items, book, by = ids()
        self.assertEqual(resume.original_of(items["e1"])["kind"], "url")
        self.assertEqual(resume.original_of(items["g1"]), {"kind": "app", "value": "Safari"})
        self.assertIsNone(resume.original_of({"id": "x"}))

    def test_only_web_addresses(self):
        item = {"id": "x", "app": "Mail", "content": {"excerpts": [{"source": {"url": "file:///etc/passwd"}}]}}
        self.assertEqual(resume.original_of(item), {"kind": "app", "value": "Mail"})


class Page(unittest.TestCase):
    def test_press_resume_and_back(self):
        reg, items, book, by = ids()
        st = page_model.new_state()
        st = page_model.press(reg, st, "go", by["Remote work essay"], items)
        st = page_model.press(reg, st, "resume", by["Remote work essay"], items)
        view = page_model.view(reg, items, st, NOW)
        self.assertEqual(view["main"]["kind"], "resume")
        st = page_model.press(reg, st, "thing", "e1", items)
        st = page_model.press(reg, st, "back", None, items)
        self.assertEqual(st["view"], "resume")
        st = page_model.press(reg, st, "go", st["pid"], items)         # the Back link on the Resume page
        self.assertEqual((st["view"], st["pid"]), ("project", by["Remote work essay"]))

    def test_project_page_marks_resume_primary_when_away(self):
        reg, items, book, by = ids()
        st = page_model.press(reg, page_model.new_state(), "go", by["Pricing page"], items)
        self.assertTrue(page_model.view(reg, items, st, NOW)["main"]["resume"]["away"])

    def test_deleted_project_falls_home(self):
        reg, items, book, by = ids()
        st = page_model.press(reg, page_model.new_state(), "resume", "p999", items)
        self.assertEqual(st["view"], "home")


if __name__ == "__main__":
    unittest.main()
