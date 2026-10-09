"""Changing projects from the window (project_actions.py): the words, Undo, the questions, the targets."""

import copy
import unittest

import project_actions as pa
import projects


def world():
    reg = projects.empty()
    ids = {"work": projects.create(reg, "Work")}
    ids["q3"] = projects.create(reg, "Q3 plan", ids["work"])
    ids["budget"] = projects.create(reg, "Budget", ids["q3"])
    ids["home"] = projects.create(reg, "Home")
    items = {}
    for iid, pid, also in (("a", ids["q3"], ()), ("b", ids["budget"], (ids["home"],)), ("c", ids["work"], ()), ("d", ids["home"], ()), ("e", None, ())):
        item = {"id": iid, "app": "Docs", "doing": "Working", "title": iid.upper(), "last_seen": "2026-10-09T10:00:00"}
        if pid:
            item["project_id"] = pid
            item["project"] = projects.get(reg, pid)["name"]
        if also:
            item["also_in"] = list(also)
        items[iid] = item
    return reg, items, ids


class DoTests(unittest.TestCase):
    def test_each_action_says_what_it_did_and_where_to_look_next(self):
        reg, items, ids = world()
        r = pa.run(reg, items, "new", name="Pricing")
        self.assertEqual((r["message"], reg["projects"][r["go"]]["name"]), ("Made “Pricing”", "Pricing"))
        r = pa.run(reg, items, "new", name="Launch", parent=ids["work"])
        self.assertEqual(r["message"], "Made “Launch” in “Work”")
        r = pa.run(reg, items, "rename", pid=ids["home"], name="House")
        self.assertEqual((r["message"], r["go"], items["d"]["project"]), ("Renamed “Home” to “House”", ids["home"], "House"))
        r = pa.run(reg, items, "move", pid=ids["budget"], parent=ids["work"])
        self.assertEqual((r["message"], r["go"]), ("Moved “Budget” into “Work”", ids["budget"]))
        r = pa.run(reg, items, "move", pid=ids["budget"], parent=None)
        self.assertEqual(r["message"], "Moved “Budget” to the top")
        r = pa.run(reg, items, "archive", pid=ids["q3"])
        self.assertEqual((r["message"], r["go"]), ("Archived “Q3 plan”", ids["work"]))
        r = pa.run(reg, items, "restore", pid=ids["q3"])
        self.assertEqual((r["message"], r["go"]), ("Brought back “Q3 plan”", ids["q3"]))
        r = pa.run(reg, items, "merge", pid=ids["q3"], target=ids["work"])
        self.assertEqual((r["message"], r["go"]), ("Merged “Q3 plan” into “Work” · 1 thing", ids["work"]))
        self.assertEqual(items["a"]["project_id"], ids["work"])

    def test_deleting_keeps_every_thing(self):
        reg, items, ids = world()
        before = set(items)
        r = pa.run(reg, items, "delete", pid=ids["work"])
        self.assertEqual(set(items), before)                                # nothing remembered is deleted (A2)
        self.assertEqual((r["message"], r["go"]), ("Deleted “Work” · 3 things kept", None))
        self.assertNotIn(ids["work"], reg["projects"])
        self.assertNotIn("project_id", items["a"])

    def test_errors_are_sentences_and_change_nothing(self):
        reg, items, ids = world()
        before = copy.deepcopy((reg, items))
        for action, args, text in (("new", {"name": "  "}, "Give the project a name."),
                                   ("new", {"name": "work"}, "There is already a project called “work” here."),
                                   ("rename", {"pid": ids["q3"], "name": ""}, "Give the project a name."),
                                   ("move", {"pid": ids["work"], "parent": ids["budget"]}, "A project cannot go inside itself."),
                                   ("merge", {"pid": ids["work"], "target": ids["q3"]}, "A project cannot be merged into itself or into something inside it."),
                                   ("archive", {"pid": "p99"}, "That project does not exist any more."),
                                   ("fly", {}, "That is not something projects can do.")):
            with self.assertRaises(ValueError) as caught:
                pa.run(reg, items, action, **args)
            self.assertEqual(str(caught.exception), text)
        self.assertEqual((reg, items), before)


class UndoTests(unittest.TestCase):
    def test_every_action_can_be_undone_exactly(self):
        for action, args in (("new", {"name": "Pricing"}), ("rename", {"pid": "p4", "name": "House"}),
                             ("move", {"pid": "p3", "parent": None}), ("archive", {"pid": "p2"}),
                             ("merge", {"pid": "p2", "target": "p4"}), ("delete", {"pid": "p1"})):
            reg, items, ids = world()
            before = copy.deepcopy((reg, items))
            result = pa.do(reg, items, action, **args)
            self.assertNotEqual((reg, items), before, action)
            pa.undo(reg, items, result["undo"])
            self.assertEqual((reg, items), before, action)

    def test_a_thing_filed_somewhere_else_since_is_left_where_you_put_it(self):
        reg, items, ids = world()
        result = pa.do(reg, items, "merge", pid=ids["q3"], target=ids["home"])
        projects.move_to(reg, items, ["a"], ids["work"])                    # filed by hand after the merge
        pa.undo(reg, items, result["undo"])
        self.assertEqual(items["a"]["project_id"], ids["work"])
        self.assertEqual(items["b"]["project_id"], ids["budget"])           # untouched things are put back

    def test_undoing_a_delete_brings_the_projects_and_their_things_back(self):
        reg, items, ids = world()
        result = pa.do(reg, items, "delete", pid=ids["work"])
        self.assertEqual(len(reg["projects"]), 1)
        pa.undo(reg, items, result["undo"])
        self.assertEqual({p["name"] for p in reg["projects"].values()}, {"Work", "Q3 plan", "Budget", "Home"})
        self.assertEqual(items["b"]["project_id"], ids["budget"])


class QuestionTests(unittest.TestCase):
    def test_merge_says_how_much_moves(self):
        reg, items, ids = world()
        p = pa.plan(reg, items, "merge", ids["q3"], ids["home"])
        self.assertEqual(p["title"], "Merge “Q3 plan” into “Home”?")
        self.assertIn("2 things and 1 sub-project move into “Home”", p["text"])
        self.assertIn("You can undo this", p["text"])
        self.assertEqual(p["button"], "Merge")

    def test_delete_promises_the_things_stay(self):
        reg, items, ids = world()
        p = pa.plan(reg, items, "delete", ids["work"])
        self.assertEqual(p["title"], "Delete “Work” and its 2 sub-projects?")
        self.assertIn("Your 3 things in them stay in LMemM, without a project. Nothing you wrote is lost.", p["text"])
        single = pa.plan(reg, items, "delete", ids["home"])
        self.assertEqual(single["title"], "Delete “Home”?")
        self.assertIn("Your 2 things in it stay", single["text"])

    def test_only_those_two_ask(self):
        reg, items, ids = world()
        with self.assertRaises(ValueError):
            pa.plan(reg, items, "rename", ids["work"])
        with self.assertRaises(ValueError):
            pa.plan(reg, items, "merge", ids["work"], ids["budget"])        # into something inside it


class TargetTests(unittest.TestCase):
    def test_a_project_can_never_go_into_itself_or_what_it_holds(self):
        reg, items, ids = world()
        names = [r["name"] for r in pa.targets(reg, ids["work"], "merge")["rows"]]
        self.assertEqual(names, ["Home"])

    def test_a_move_offers_the_top_level_but_not_where_it_already_is(self):
        reg, items, ids = world()
        rows = pa.targets(reg, ids["budget"], "move")["rows"]
        self.assertEqual([r["name"] for r in rows], ["Top level", "Home", "Work"])
        self.assertIsNone(rows[0]["id"])                                     # q3 is its parent: not offered
        top = pa.targets(reg, ids["home"], "move")["rows"]
        self.assertNotIn("Top level", [r["name"] for r in top])              # already at the top

    def test_archived_places_are_not_offered_and_a_search_narrows(self):
        reg, items, ids = world()
        projects.archive(reg, ids["q3"])
        names = [r["name"] for r in pa.targets(reg, ids["home"], "merge")["rows"]]
        self.assertEqual(names, ["Work"])                                    # Q3 plan and Budget are out of sight
        found = pa.targets(reg, ids["budget"], "merge", "WORK")["rows"]
        self.assertEqual([r["path"] for r in found], ["Work"])

    def test_a_merged_projects_old_name_still_finds_it(self):
        reg, items, ids = world()
        projects.merge(reg, items, ids["home"], ids["work"])
        found = pa.targets(reg, ids["budget"], "move", "home")["rows"]
        self.assertEqual([r["name"] for r in found], ["Work"])

    def test_a_long_list_is_cut_and_says_so(self):
        reg = projects.empty()
        first = projects.create(reg, "First")
        for n in range(60):
            projects.create(reg, f"P{n:02}")
        t = pa.targets(reg, first, "merge")
        self.assertEqual((len(t["rows"]), t["more"]), (pa.TARGETS_SHOWN, 20))


class WiringTests(unittest.TestCase):
    """window.py and the tracker need a Mac to import, so the hand-offs are checked from the source."""

    def source(self, name):
        import ast
        import os
        with open(os.path.join(os.path.dirname(__file__), "..", "src", name)) as fh:
            return ast.parse(fh.read())

    def methods(self, name):
        import ast
        return {n.name: ast.unparse(n) for c in self.source(name).body if hasattr(c, "body") and c.__class__.__name__ == "ClassDef"
                for n in c.body if n.__class__.__name__ == "FunctionDef"}

    def test_the_tracker_runs_actions_under_the_lock_and_saves_both_files(self):
        m = self.methods("tracker.py")
        do = m["window_project"]
        self.assertIn("project_actions.do(reg, self.items, action, **args)", do)
        for needle in ("with self.lock", "projects.load()", "projects.save(reg)", "self.save(force=True)"):
            self.assertIn(needle, do)
            self.assertIn(needle, m["window_project_undo"])
        self.assertIn("project_actions.undo(reg, self.items, undo)", m["window_project_undo"])
        self.assertIn("self.window_project, self.window_project_undo", m["open_window"])

    def test_every_action_the_window_asks_for_is_one_this_module_does(self):
        import re
        with open(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "src", "window.py")) as fh:
            source = fh.read()
        asked = set(re.findall(r'project_action\("([a-z]+)"', source)) | set(re.findall(r'open_name\("([a-z]+)"', source))
        asked |= set(re.findall(r'open_pick\("([a-z]+)"', source)) | set(re.findall(r'open_ask\("([a-z]+)"', source))
        self.assertTrue({"new", "rename", "move", "archive", "restore", "merge", "delete"} <= asked, asked)
        self.assertTrue(asked <= set(pa.ACTIONS), asked)


if __name__ == "__main__":
    unittest.main()
