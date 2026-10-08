"""The pill card's view model: what it shows for a thing, its project, and ticked notes."""

import unittest

import notes


def item(iid, title, note_texts, project="Q3"):
    return {"id": iid, "kind": "code_file", "title": title, "doing": title, "app": "Docs",
            "state": {"project": project}, "visits": 1, "seconds": 60, "last_seen": "2026-10-06T10:00:00",
            "notes": [{"at": f"2026-10-06T10:0{n}:00", "text": t} for n, t in enumerate(note_texts)]}


def card(items, current="a"):
    return notes.card({i["id"]: i for i in items}, current)


class CardViewTests(unittest.TestCase):
    def setUp(self):
        self.a = item("a", "Q3 plan", ["add a pricing table", "ask Rahul"])
        self.b = item("b", "Pricing sheet", ["check discounts"])

    def test_here_shows_this_things_open_notes_and_counts_the_rest(self):
        view = notes.card_view(card([self.a, self.b]))
        self.assertEqual(view["title"], "Q3 plan")
        self.assertEqual([r["text"] for r in view["rows"]], ["add a pricing table", "ask Rahul"])
        self.assertEqual(view["more"], 1)

    def test_pill_counts_only_this_thing(self):
        self.assertEqual(notes.pill_summary(card([self.a, self.b])), (2, "add a pricing table"))
        self.assertEqual(notes.pill_summary(card([self.a, self.b], "b")), (1, "check discounts"))
        self.assertEqual(notes.pill_summary(None), (0, ""))

    def test_ticked_note_stays_struck_through_while_fading_then_leaves(self):
        nid = notes.note_id(self.a["notes"][0])
        self.a["notes_done"] = {nid: "2026-10-06T11:00:00"}
        data = card([self.a, self.b])
        gone = notes.card_view(data)
        self.assertEqual([r["text"] for r in gone["rows"]], ["ask Rahul"])
        fading = notes.card_view(data, fading={nid})
        self.assertEqual([(r["text"], r["done"]) for r in fading["rows"]],
                         [("ask Rahul", False), ("add a pricing table", True)])

    def test_project_view_groups_by_thing_and_hides_done_until_asked(self):
        nid = notes.note_id(self.a["notes"][0])
        self.a["notes_done"] = {nid: "2026-10-06T11:00:00"}
        data = card([self.a, self.b])
        view = notes.card_view(data, "project")
        self.assertEqual([g for g, _ in view["groups"]], ["Q3 plan", "Pricing sheet"])
        self.assertEqual((view["done"], view["done_count"]), ([], 1))
        self.assertEqual(len(notes.card_view(data, "project", show_done=True)["done"]), 1)

    def test_nothing_in_front(self):
        self.assertEqual(notes.card_view(None), {"empty": True})


if __name__ == "__main__":
    unittest.main()
