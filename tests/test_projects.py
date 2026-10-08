"""Filing things into projects: by hand, by accepting a suggestion, and the picker's view."""

import unittest

import notes


def item(iid, title, last="2026-10-06T10:00:00", **extra):
    return {"id": iid, "kind": "document", "title": title, "doing": title, "app": "Docs",
            "visits": 1, "seconds": 60, "last_seen": last, **extra}


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.items = {i["id"]: i for i in (
            item("a", "Q3 plan", notes=[{"at": "2026-10-06T10:00:00", "text": "add pricing"}]),
            item("b", "Pricing sheet", "2026-10-06T10:05:00"),
            item("c", "Revenue model", "2026-10-06T09:50:00"),
            item("d", "Old thing", "2026-10-01T09:50:00"))}

    def test_a_chosen_project_wins_over_the_guess(self):
        self.assertEqual(notes.project_of(self.items["a"]), "Q3 plan")
        notes.set_project(self.items, ["a", "b"], "  Pricing ")
        self.assertEqual([notes.project_of(self.items[i]) for i in "ab"], ["Pricing", "Pricing"])
        data = notes.card(self.items, "a")
        self.assertEqual((data["project"], data["things"]), ("Pricing", 2))

    def test_unknown_ids_and_blank_names_do_nothing(self):
        self.assertEqual(notes.set_project(self.items, ["zzz"], "Pricing"), [])
        self.assertEqual(notes.set_project(self.items, ["a"], "   "), [])
        self.assertNotIn("project", self.items["a"])

    def test_clear_takes_it_back_out(self):
        notes.set_project(self.items, ["a"], "Pricing")
        self.assertEqual(notes.clear_project(self.items, ["a", "b"]), ["a"])
        self.assertEqual(notes.project_of(self.items["a"]), "Q3 plan")

    def test_project_names_most_recent_first_and_only_ones_you_made(self):
        notes.set_project(self.items, ["a", "d"], "Old")
        notes.set_project(self.items, ["b"], "Pricing")
        self.assertEqual([(p["name"], p["things"]) for p in notes.project_names(self.items)],
                         [("Pricing", 1), ("Old", 2)])

    def test_open_now_offers_recent_others_not_already_in_the_project(self):
        notes.set_project(self.items, ["a", "b"], "Pricing")
        near = notes.open_now(self.items, "a", "2026-10-06T10:10:00")
        self.assertEqual([n["id"] for n in near], ["c"])          # b is in it already, d is old

    def test_picker_always_offers_new_and_filters_by_typing(self):
        notes.set_project(self.items, ["b"], "Pricing")
        notes.set_project(self.items, ["c"], "Onboarding")
        view = notes.picker_view(self.items, "a", "", "2026-10-06T10:10:00")
        self.assertEqual((view["new"], [r["name"] for r in view["rows"]]), ("", ["Pricing", "Onboarding"]))
        typed = notes.picker_view(self.items, "a", "pri", "2026-10-06T10:10:00")
        self.assertEqual(([r["name"] for r in typed["rows"]], typed["new"]), (["Pricing"], "pri"))
        exact = notes.picker_view(self.items, "a", "pricing", "2026-10-06T10:10:00")
        self.assertEqual(exact["new"], "")                           # it exists: no duplicate offer

    def test_picker_marks_where_it_already_is(self):
        notes.set_project(self.items, ["a"], "Pricing")
        view = notes.picker_view(self.items, "a", "", "2026-10-06T10:10:00")
        self.assertEqual((view["current"], view["rows"][0]["here"]), ("Pricing", True))
        self.assertIsNone(notes.picker_view(self.items, "nope"))

    def test_declined_group_is_remembered(self):
        notes.decline_project(self.items, ["a", "b"], "Pricing")
        notes.decline_project(self.items, ["a"], "Pricing")
        self.assertEqual(self.items["a"]["declined_projects"], ["Pricing"])
        self.assertTrue(notes.was_declined(self.items, ["b", "c"], "Pricing"))
        self.assertFalse(notes.was_declined(self.items, ["c"], "Pricing"))
        self.assertFalse(notes.was_declined(self.items, ["a"], "Other"))

    def test_suggestion_view_words_first_then_just_the_mark(self):
        sug = {"name": "Pricing", "ids": ["a", "b", "c"], "reason": "Opened together"}
        first = notes.suggestion_view(sug, self.items, answered=0)
        self.assertEqual((first["first_time"], first["peek"]), (True, "Pricing · 3 things"))
        self.assertFalse(notes.suggestion_view(sug, self.items, answered=3)["first_time"])

    def test_suggestion_needs_two_things_that_still_exist(self):
        self.assertIsNone(notes.suggestion_view(None, self.items))
        self.assertIsNone(notes.suggestion_view({"name": "X", "ids": ["a", "gone"]}, self.items))


if __name__ == "__main__":
    unittest.main()
