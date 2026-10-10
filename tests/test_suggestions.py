"""What LMemM proposes and you decide (suggestions.py): holding, tidying, answering, Undo."""

import copy
import unittest
from datetime import datetime

import project_actions as pa
import projects
import suggestions as sg
from test_project_actions import world

NOW = datetime(2026, 10, 9, 12, 0, 0)


class OfferTests(unittest.TestCase):
    def test_a_project_needs_two_known_things_and_is_not_offered_twice(self):
        reg, items, ids = world()
        sug = sg.empty()
        self.assertIsNone(sg.offer_project(sug, items, "Trip", ["a"]))
        self.assertIsNone(sg.offer_project(sug, items, "Trip", ["a", "zzz"]))
        first = sg.offer_project(sug, items, "Trip", ["a", "e"])
        self.assertEqual(sg.offer_project(sug, items, "trip", ["c", "d"]), first)       # same name: still one
        self.assertEqual(sg.offer_project(sug, items, "Other", ["e", "a"]), first)      # same things: still one
        self.assertEqual(len(sug["projects"]), 1)

    def test_a_dismissed_project_never_comes_back(self):
        reg, items, ids = world()
        sug = sg.empty()
        entry = sg.offer_project(sug, items, "Trip", ["a", "e"])
        r = sg.run(reg, items, sug, "dismiss_project", entry["id"])
        self.assertEqual((r["message"], r["stay"], sug["projects"]), ("Won't suggest “Trip” again", True, []))
        self.assertIsNone(sg.offer_project(sug, items, "Trip", ["a", "e"]))

    def test_things_for_a_project_skip_what_makes_no_sense(self):
        reg, items, ids = world()
        sug = sg.empty()
        items["d"]["not_in"] = [ids["q3"]]
        entry = sg.offer_items(sug, reg, items, ids["q3"], ["a", "c", "d", "e", "zzz"])      # a is in Q3 already, d refused it
        self.assertEqual(entry["ids"], ["c", "e"])
        sg.offer_items(sug, reg, items, ids["q3"], ["e", "b"])                          # joins the same entry
        self.assertEqual((len(sug["items"]), sug["items"][0]["ids"]), (1, ["c", "e", "b"]))
        self.assertIsNone(sg.offer_items(sug, reg, items, ids["home"], ["d", "b"]))      # d is in Home, b is also in Home
        with self.assertRaises(ValueError):
            sg.offer_items(sug, reg, items, "nope", ["e"])
        projects.archive(reg, ids["q3"])
        self.assertIsNone(sg.offer_items(sg.empty(), reg, items, ids["q3"], ["e"]))

    def test_the_list_tidies_itself_when_things_change(self):
        reg, items, ids = world()
        sug = sg.empty()
        sg.offer_items(sug, reg, items, ids["q3"], ["c", "e"])
        sg.offer_project(sug, items, "Trip", ["d", "e"])
        projects.move_to(reg, items, ["e"], ids["q3"])                                  # filed by hand since
        del items["d"]
        v = sg.view(sug, reg, items, NOW)
        self.assertEqual((v["count"], [t["id"] for t in v["items"][0]["things"]], v["projects"]), (1, ["c"], []))
        projects.delete(reg, items, ids["q3"])
        self.assertEqual(sg.view(sug, reg, items, NOW)["count"], 0)


class AnswerTests(unittest.TestCase):
    def test_creating_files_the_things_and_goes_to_the_new_project(self):
        reg, items, ids = world()
        sug = sg.empty()
        entry = sg.offer_project(sug, items, "Trip", ["a", "e"])
        r = sg.run(reg, items, sug, "accept_project", entry["id"], name="  Japan trip ")
        self.assertEqual((r["message"], reg["projects"][r["go"]]["name"]), ("Made “Japan trip” · 2 things", "Japan trip"))
        self.assertEqual((items["a"]["project_id"], items["e"]["project_id"]), (r["go"], r["go"]))
        self.assertEqual(sug["projects"], [])

    def test_add_and_not_here_can_answer_one_thing_or_all(self):
        reg, items, ids = world()
        sug = sg.empty()
        entry = sg.offer_items(sug, reg, items, ids["q3"], ["c", "d", "e"])
        r = sg.run(reg, items, sug, "accept_items", entry["id"], ids=["c"])
        self.assertEqual((r["message"], items["c"]["also_in"], r["stay"]), ("Added “C” to “Q3 plan”", [ids["q3"]], True))
        r = sg.run(reg, items, sug, "reject_items", entry["id"], ids=["d"])
        self.assertEqual((r["message"], items["d"]["not_in"]), ("“D” won't be suggested for “Q3 plan” again", [ids["q3"]]))
        r = sg.run(reg, items, sug, "accept_items", entry["id"])
        self.assertEqual((r["message"], sug["items"]), ("Added “E” to “Q3 plan”", []))
        self.assertEqual(items["e"]["project_id"], ids["q3"])                           # it had no project: this is its main

    def test_an_answer_that_is_already_gone_is_a_sentence(self):
        reg, items, ids = world()
        for kw in ({"action": "accept_project", "sid": "s9"}, {"action": "reject_items", "sid": "s9"}):
            with self.assertRaises(ValueError) as e:
                sg.run(reg, items, sg.empty(), **kw)
            self.assertIn("gone already", str(e.exception))

    def test_the_pill_answering_clears_the_window_too(self):
        reg, items, ids = world()
        sug = sg.empty()
        sg.offer_project(sug, items, "Trip", ["a", "e"])
        sg.offer_items(sug, reg, items, ids["home"], ["a", "e", "c"])
        sg.drop_ids(sug, ["a"])
        self.assertEqual((sug["projects"], sug["items"][0]["ids"]), ([], ["e", "c"]))

    def test_undo_brings_the_proposal_back_with_the_things_as_they_were(self):
        reg, items, ids = world()
        sug = sg.empty()
        entry = sg.offer_project(sug, items, "Trip", ["a", "e"])
        before = copy.deepcopy((reg, items, sug))
        r = pa.do(reg, items, "accept_project", sug=sug, sid=entry["id"])
        self.assertEqual(sug["projects"], [])
        pa.undo(reg, items, r["undo"], sug)
        self.assertEqual((reg, items, sug), before)
        r = pa.do(reg, items, "dismiss_project", sug=sug, sid=entry["id"])
        pa.undo(reg, items, r["undo"], sug)
        self.assertEqual(sug, before[2])
        self.assertEqual(sg.view(sug, reg, items, NOW)["count"], 1)                   # and tidy() does not drop it again


class WindowWiringTests(unittest.TestCase):
    def test_every_answer_the_window_sends_is_a_real_one(self):
        import os
        import re
        with open(os.path.join(os.path.dirname(__file__), "..", "src", "window.py")) as fh:
            source = fh.read()
        sent = set(re.findall(r'self\.answer\("([a-z_]+)"', source))
        self.assertEqual(sent, set(sg.ACTIONS))


if __name__ == "__main__":
    unittest.main()
