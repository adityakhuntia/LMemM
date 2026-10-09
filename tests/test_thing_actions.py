"""Putting things in projects from the window (thing_actions.py): the words, Undo, the question, the places."""

import copy
import unittest

import notes
import project_actions as pa
import projects
import thing_actions as ta
from test_project_actions import world


class DoTests(unittest.TestCase):
    def test_move_also_and_not_in_say_what_happened_and_leave_the_page_alone(self):
        reg, items, ids = world()
        r = pa.run(reg, items, "assign", ids=["e"], pid=ids["home"])
        self.assertEqual((r["message"], r["stay"], items["e"]["project_id"]), ("Moved “E” to “Home”", True, ids["home"]))
        r = pa.run(reg, items, "also", ids=["e"], pid=ids["work"])
        self.assertEqual((r["message"], items["e"]["also_in"]), ("Added “E” to “Work”", [ids["work"]]))
        r = pa.run(reg, items, "not_this", ids=["e", "d"], pid=ids["home"])
        self.assertEqual(r["message"], "Took 2 things out of “Home”. It won't be suggested there again")
        self.assertEqual(items["d"]["not_in"], [ids["home"]])
        self.assertEqual(items["e"]["project_id"], ids["work"])             # the "also in" took over

    def test_forget_removes_only_what_was_asked_and_undo_brings_it_back_whole(self):
        reg, items, ids = world()
        notes.record(items, items["a"], [], ("item", "a"), "call Sam", "2026-10-09T10:00:00")
        whole = copy.deepcopy(items["a"])
        r = pa.do(reg, items, "forget", ids=["a", "missing"])
        self.assertEqual((r["message"], sorted(items)), ("Forgot “A”", ["b", "c", "d", "e"]))
        pa.undo(reg, items, r["undo"])
        self.assertEqual(items["a"], whole)

    def test_undo_leaves_a_thing_you_filed_since(self):
        reg, items, ids = world()
        r = pa.do(reg, items, "assign", ids=["e"], pid=ids["home"])
        projects.move_to(reg, items, ["e"], ids["work"])
        pa.undo(reg, items, r["undo"])
        self.assertEqual(items["e"]["project_id"], ids["work"])
        r = pa.do(reg, items, "assign", ids=["e"], pid=ids["home"])
        pa.undo(reg, items, r["undo"])
        self.assertEqual(items["e"]["project_id"], ids["work"])

    def test_gone_things_and_unknown_projects_are_sentences(self):
        reg, items, ids = world()
        before = copy.deepcopy((reg, items))
        for args in ({"action": "assign", "ids": ["zzz"], "pid": ids["home"]}, {"action": "forget", "ids": []}):
            with self.assertRaises(ValueError) as e:
                pa.do(reg, items, **args)
            self.assertIn("gone already", str(e.exception))
        with self.assertRaises(ValueError):
            pa.do(reg, items, "assign", ids=["e"], pid="nope")
        self.assertEqual((reg, items), before)


class AskTests(unittest.TestCase):
    def test_forget_says_what_goes_with_it(self):
        reg, items, ids = world()
        notes.record(items, items["a"], [], ("item", "a"), "call Sam", "2026-10-09T10:00:00")
        one = ta.plan_forget(items, ["a"])
        self.assertEqual(one["title"], "Forget “A”?")
        self.assertIn("its 1 open note", one["text"])
        self.assertEqual(ta.plan_forget(items, ["a", "b"])["title"], "Forget 2 things?")
        self.assertEqual(one["button"], "Forget")


class PlaceTests(unittest.TestCase):
    def names(self, reg, items, ids, kind, query=""):
        return [r["name"] for r in ta.places(reg, items, ids, kind, query)["rows"]]

    def test_a_place_everything_selected_is_already_in_is_not_offered(self):
        reg, items, ids = world()
        self.assertNotIn("Q3 plan", self.names(reg, items, ["a"], "assign"))
        self.assertIn("Q3 plan", self.names(reg, items, ["a", "c"], "assign"))
        self.assertNotIn("Home", self.names(reg, items, ["b"], "also"))        # b is also in Home
        self.assertNotIn("Budget", self.names(reg, items, ["b"], "assign"))

    def test_archived_places_and_what_is_inside_them_are_not_offered(self):
        reg, items, ids = world()
        projects.archive(reg, ids["q3"])
        self.assertEqual(self.names(reg, items, ["e"], "assign"), ["Home", "Work"])

    def test_typing_narrows_by_path_or_old_name(self):
        reg, items, ids = world()
        self.assertEqual(self.names(reg, items, ["e"], "assign", "q3"), ["Q3 plan", "Budget"])
        projects.merge(reg, items, ids["home"], ids["work"])
        self.assertEqual(self.names(reg, items, ["e"], "assign", "home"), ["Work"])


class WhyTests(unittest.TestCase):
    def test_it_only_says_what_is_stored(self):
        reg, items, ids = world()
        self.assertEqual(ta.why(reg, items["e"]), ["Not in any project yet. Move it to one and it stays there."])
        projects.not_this(reg, items, ["b"], ids["q3"])
        self.assertEqual(ta.why(reg, items["b"]), ["Main project: Work › Q3 plan › Budget.", "Also in Home.", "Never suggested for Q3 plan."])
        projects.add_also(reg, items, ["a"], ids["home"])
        self.assertEqual(ta.why(reg, items["a"]), ["Main project: Work › Q3 plan.", "Also in Home."])


if __name__ == "__main__":
    unittest.main()


class PillTests(unittest.TestCase):
    """The pill files by name; the window shows the tree. They have to say the same thing (T6)."""

    def test_filing_from_the_pill_moves_the_main_project_in_the_tree(self):
        reg, items, ids = world()
        self.assertEqual(ta.file_by_name(reg, items, ["a", "zzz"], " home "), ["a"])
        self.assertEqual((items["a"]["project_id"], items["a"]["project"]), (ids["home"], "Home"))
        ta.file_by_name(reg, items, ["e"], "Brand new")
        self.assertEqual(reg["projects"][items["e"]["project_id"]]["name"], "Brand new")
        self.assertEqual(ta.file_by_name(reg, items, ["e"], "  "), [])

    def test_taking_it_out_from_the_pill_clears_the_tree_too(self):
        reg, items, ids = world()
        self.assertEqual(ta.unfile_main(reg, items, ["b", "e"]), ["b"])
        self.assertEqual(items["b"]["project_id"], ids["home"])                # its "also in" took over
        self.assertNotIn("project_id", items["e"])

    def test_not_this_project_from_the_pill_is_remembered_for_the_window_too(self):
        reg, items, ids = world()
        ta.decline_by_name(reg, items, ["e"], "home")
        self.assertEqual(items["e"]["not_in"], [ids["home"]])
        ta.decline_by_name(reg, items, ["e"], "Not a project")                # a name that is only a suggestion yet
        self.assertEqual(items["e"]["not_in"], [ids["home"]])


class WindowWiringTests(unittest.TestCase):
    """window.py needs a Mac to import, so what it calls is checked from its source."""

    def source(self):
        import os
        with open(os.path.join(os.path.dirname(__file__), "..", "src", "window.py")) as fh:
            return fh.read()

    def test_every_method_the_window_calls_on_itself_exists(self):
        import ast
        tree = ast.parse(self.source())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
        defined = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        called = {n.func.attr for n in ast.walk(cls) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and isinstance(n.func.value, ast.Name) and n.func.value.id == "self"}
        attrs = {n.attr for n in ast.walk(cls) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                 and n.value.id == "self" and isinstance(n.ctx, ast.Store)}
        missing = {c for c in called if c not in defined and c not in attrs}
        self.assertEqual(missing, set())

    def test_every_thing_action_the_window_sends_is_a_real_one_and_every_dialog_kind_is_drawn(self):
        import re
        source = self.source()
        sent = set(re.findall(r'thing_action\("([a-z_]+)"', source)) | set(re.findall(r'open_thing_pick\("([a-z_]+)"', source))
        self.assertEqual(sent - {"assign", "also", "not_this", "forget"}, set())
        self.assertTrue({"assign", "also", "not_this", "forget"} <= sent, sent)
        for kind in set(re.findall(r'"kind": "([a-z]+)"', source)) & {"name", "menu", "pick", "ask", "tmenu", "tpick", "task"}:
            self.assertIn(f'd["kind"] == "{kind}"', source, kind)
