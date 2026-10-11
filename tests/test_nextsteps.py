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

    def test_at_most_five_wait_and_old_ones_go(self):
        doc = nextsteps.empty()
        for n in range(8):
            nextsteps.ingest(doc, result(tasks=[{"title": "t", "open": f"Step number {n} to take next", "items": ["a"]}], links=[]),
                             items(), NOW + timedelta(minutes=n))
        self.assertEqual(nextsteps.view(doc, items(), NOW + timedelta(minutes=8))["count"], nextsteps.MAX_OPEN)
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


if __name__ == "__main__":
    unittest.main()
