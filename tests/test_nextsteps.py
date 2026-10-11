"""nextsteps.py: the safe next step the pill offers - suggest only, few, fresh, said once."""

import unittest
from datetime import datetime, timedelta

import nextsteps
from test_labels import TmpPaths, thing

NOW = datetime(2026, 10, 11, 12, 0, 0)


def items():
    return {"a": thing("a", app="ChatGPT", title="Create Follow Ups"), "b": thing("b", app="script.google.com", title="Auto Send"),
            "c": thing("c", app="Gmail", title="scheduled")}


def result(**kw):
    base = {"tasks": [{"title": "Verify the automation", "open": "Check the trigger runs on a weekday", "items": ["a", "b"]}],
            "links": [{"items": ["a", "b"], "why": "The reminder wording in the chat is what the script sends"}]}
    base.update(kw)
    return base


class NextStepTests(TmpPaths):
    def test_a_task_gives_a_next_step_and_a_pair_gives_a_link(self):
        doc = nextsteps.empty()
        added = nextsteps.ingest(doc, result(), items(), NOW)
        self.assertEqual({s["kind"] for s in added}, {"next", "link"})
        v = nextsteps.view(doc, items(), NOW)
        self.assertEqual(v["count"], 2)
        self.assertEqual(v["steps"][0]["things"][0]["app"] in ("ChatGPT", "script.google.com"), True)

    def test_the_same_sentence_is_kept_once_and_refreshed(self):
        doc = nextsteps.empty()
        nextsteps.ingest(doc, result(), items(), NOW)
        again = nextsteps.ingest(doc, result(), items(), NOW + timedelta(minutes=30))
        self.assertEqual(again, [])
        self.assertEqual(len(doc["steps"]), 2)

    def test_an_answered_step_never_comes_back_that_day(self):
        doc = nextsteps.empty()
        nextsteps.ingest(doc, result(), items(), NOW)
        nextsteps.answer(doc, "n1", "dismissed")
        nextsteps.ingest(doc, result(), items(), NOW + timedelta(minutes=30))
        self.assertEqual(nextsteps.view(doc, items(), NOW + timedelta(minutes=30))["count"], 1)
        with self.assertRaises(ValueError):
            nextsteps.answer(doc, "n1", "done")             # already answered: nothing changes

    def test_a_link_needs_two_different_things_that_still_exist(self):
        doc = nextsteps.empty()
        nextsteps.ingest(doc, result(tasks=[], links=[{"items": ["a", "a"], "why": "x y"}, {"items": ["a", "zz"], "why": "gone"}]),
                         items(), NOW)
        self.assertEqual(doc["steps"], [])
        nextsteps.ingest(doc, result(tasks=[]), items(), NOW)
        left = {k: v for k, v in items().items() if k != "b"}
        self.assertEqual(nextsteps.view(doc, left, NOW)["count"], 0)

    def test_each_kind_is_capped_and_old_ones_go(self):
        doc = nextsteps.empty()
        for n in range(8):
            nextsteps.ingest(doc, result(tasks=[{"title": "t", "open": f"Step number {n} to take next", "items": ["a"]}], links=[]),
                             items(), NOW + timedelta(minutes=n))
        self.assertEqual(nextsteps.view(doc, items(), NOW + timedelta(minutes=8))["count"], nextsteps.PER_KIND["next"])
        self.assertEqual(nextsteps.view(doc, items(), NOW + timedelta(hours=13))["count"], 0)

    def test_addresses_are_scrubbed_from_a_step(self):
        doc = nextsteps.empty()
        nextsteps.ingest(doc, result(tasks=[{"title": "t", "open": "Email maria@example.com the file", "items": ["a"]}], links=[]), items(), NOW)
        self.assertNotIn("maria@", doc["steps"][0]["text"])

    def test_it_saves_and_loads(self):
        doc = nextsteps.empty()
        nextsteps.ingest(doc, result(), items(), NOW)
        nextsteps.save(doc)
        self.assertEqual(len(nextsteps.load()["steps"]), 2)


def stored_tasks(at):
    return {"s": {"at": at.isoformat(timespec="seconds"), "tasks": [
        {"title": "Verify the follow-up automation", "goal": "Find out who scheduled the emails", "stage": "testing",
         "open": "Check the trigger runs on a weekday", "last_wrote": "The execution from Oct 9 onwards", "items": ["a", "b"]}]}}


def old(iid, hours, **kw):
    it = items()[iid]
    it["last_seen"] = (NOW - timedelta(hours=hours)).isoformat(timespec="seconds")
    it.update(kw)
    return it


class RecallTests(TmpPaths):
    def world(self, hours_a=5, hours_b=5, **kw):
        w = items()
        w["a"] = old("a", hours_a)
        w["b"] = old("b", hours_b)
        w.update(kw)
        return w

    def test_coming_back_to_a_task_after_hours_offers_to_pick_it_up(self):
        doc = nextsteps.empty()
        added = nextsteps.refresh(doc, self.world(), stored_tasks(NOW - timedelta(hours=5)), NOW, front_id="a")
        step = [s for s in added if s["kind"] == "resume"][0]
        self.assertEqual(step["text"], "Back to “Verify the follow-up automation”")
        self.assertEqual(step["detail"]["last_wrote"], "The execution from Oct 9 onwards")
        self.assertEqual(step["detail"]["open"], "Check the trigger runs on a weekday")
        self.assertEqual(len(step["detail"]["things"]), 2)

    def test_no_pick_up_while_you_are_still_in_the_task_or_on_something_else(self):
        w = self.world()
        self.assertFalse([s for s in nextsteps.refresh(nextsteps.empty(), w, stored_tasks(NOW - timedelta(minutes=20)), NOW, front_id="a")
                          if s["kind"] == "resume"])
        self.assertFalse([s for s in nextsteps.refresh(nextsteps.empty(), w, stored_tasks(NOW - timedelta(hours=5)), NOW, front_id="c")
                          if s["kind"] == "resume"])

    def test_a_stale_task_with_an_open_question_is_left_hanging_until_you_go_back(self):
        doc = nextsteps.empty()
        w = self.world()
        added = nextsteps.refresh(doc, w, stored_tasks(NOW - timedelta(hours=5)), NOW, front_id="c")
        self.assertIn("Still open in “Verify the follow-up automation”: Check the trigger runs on a weekday",
                      [s["text"] for s in added])
        nextsteps.refresh(doc, w, stored_tasks(NOW - timedelta(hours=5)), NOW + timedelta(minutes=1), front_id="a")
        self.assertFalse([s for s in doc["steps"] if s["kind"] == "hanging"])          # you went back: it is gone

    def test_an_unsent_draft_and_an_old_open_note_are_left_hanging(self):
        w = self.world()
        w["c"] = old("c", 2, kind="writing_email", state={"subject": "Proposal for the foundation", "draft": "Dear team"})
        w["a"] = old("a", 6, notes=[{"at": "2026-10-11T05:00:00", "text": "Ask Rahul about the vendor list", "while": "x"}])
        added = nextsteps.refresh(nextsteps.empty(), w, {}, NOW, front_id="b")
        texts = [s["text"] for s in added]
        self.assertIn("Unsent draft: “Proposal for the foundation”", texts)
        self.assertTrue(any(t.startswith("A note on “Create Follow Ups”: Ask Rahul") for t in texts))

    def test_the_card_order_is_pick_up_then_hanging_then_next_then_link(self):
        doc = nextsteps.empty()
        nextsteps.ingest(doc, result(), items(), NOW - timedelta(hours=6))
        w = self.world()
        w["c"] = old("c", 2, kind="writing_email", state={"subject": "Proposal"})
        nextsteps.refresh(doc, w, stored_tasks(NOW - timedelta(hours=5)), NOW, front_id="a")
        kinds = [s["kind"] for s in nextsteps.view(doc, w, NOW)["steps"]]
        self.assertEqual(kinds, sorted(kinds, key=nextsteps.PRIORITY.index))
        self.assertEqual(kinds[0], "resume")

    def test_refresh_leaves_the_models_steps_alone(self):
        doc = nextsteps.empty()
        nextsteps.ingest(doc, result(), items(), NOW)
        nextsteps.refresh(doc, items(), {}, NOW, front_id="a")
        self.assertEqual({s["kind"] for s in doc["steps"]}, {"next", "link"})


if __name__ == "__main__":
    unittest.main()
