"""The project tree (projects.py): any depth, a thing in several projects, merge, delete, counts.
Rules R12-R15."""

import random
import tempfile
import unittest

import config
import projects


def item(iid, last="2026-10-06T10:00:00", **extra):
    return {"id": iid, "kind": "document", "title": iid, "doing": iid, "app": "Docs",
            "visits": 1, "seconds": 60, "last_seen": last, **extra}


def things(*ids):
    return {i: item(i, last=f"2026-10-06T10:0{n}:00") for n, i in enumerate(ids)}


class TreeTests(unittest.TestCase):
    def setUp(self):
        self.reg = projects.empty()
        self.a = projects.create(self.reg, "Pricing")
        self.b = projects.create(self.reg, "Q3 launch", self.a)
        self.c = projects.create(self.reg, "Partner outreach", self.b)
        self.d = projects.create(self.reg, "India", self.c)

    def test_nesting_goes_as_deep_as_you_like(self):
        parent = self.d
        for n in range(60):
            parent = projects.create(self.reg, f"Level {n}", parent)
        self.assertEqual(projects.depth(self.reg, parent), 63)
        self.assertEqual(projects.path_names(self.reg, self.d), ["Pricing", "Q3 launch", "Partner outreach", "India"])

    def test_a_name_is_trimmed_and_must_not_repeat_in_the_same_place(self):
        pid = projects.create(self.reg, "  Hiring   plan ")
        self.assertEqual(projects.get(self.reg, pid)["name"], "Hiring plan")
        with self.assertRaises(ValueError) as e:
            projects.create(self.reg, "hiring PLAN")
        self.assertIn("already a project called", str(e.exception))
        projects.create(self.reg, "Hiring plan", self.a)                  # same name, another place: fine
        with self.assertRaises(ValueError):
            projects.create(self.reg, "   ")

    def test_rename_keeps_names_unique_among_siblings(self):
        other = projects.create(self.reg, "Press kit", self.b)
        with self.assertRaises(ValueError):
            projects.rename(self.reg, other, "partner outreach")
        projects.rename(self.reg, other, "Press kit v2")
        projects.rename(self.reg, other, "PRESS KIT V2")                 # your own name, new case: fine
        self.assertEqual(projects.get(self.reg, other)["name"], "PRESS KIT V2")

    def test_rename_updates_the_name_older_code_reads(self):
        items = things("x")
        projects.move_to(self.reg, items, ["x"], self.b)
        projects.rename(self.reg, self.b, "Launch Q3", items)
        self.assertEqual(items["x"]["project"], "Launch Q3")

    def test_move_never_makes_a_loop(self):
        with self.assertRaises(ValueError):
            projects.move(self.reg, self.a, self.d)
        with self.assertRaises(ValueError):
            projects.move(self.reg, self.a, self.a)
        projects.move(self.reg, self.d, None)
        self.assertIsNone(projects.get(self.reg, self.d)["parent"])
        self.assertEqual(projects.descendants(self.reg, self.a), [self.b, self.c])

    def test_move_refuses_a_name_clash_at_the_destination(self):
        twin = projects.create(self.reg, "India")
        with self.assertRaises(ValueError):
            projects.move(self.reg, twin, self.c)

    def test_archive_hides_everything_inside_and_restore_brings_the_way_back(self):
        projects.archive(self.reg, self.b)
        self.assertTrue(projects.hidden(self.reg, self.d))
        self.assertFalse(projects.hidden(self.reg, self.a))
        projects.restore(self.reg, self.d)                                  # the parent comes back too
        self.assertFalse(projects.hidden(self.reg, self.d))
        self.assertFalse(projects.get(self.reg, self.b)["archived"])

    def test_find_looks_in_one_place_or_everywhere_and_ignores_case(self):
        self.assertEqual(projects.find(self.reg, "pricing"), self.a)
        self.assertIsNone(projects.find(self.reg, "india"))
        self.assertEqual(projects.find(self.reg, " INDIA ", any_depth=True), self.d)
        self.assertIsNone(projects.find(self.reg, ""))


class ThingsTests(unittest.TestCase):
    def setUp(self):
        self.reg = projects.empty()
        self.a = projects.create(self.reg, "Pricing")
        self.b = projects.create(self.reg, "Q3 launch", self.a)
        self.c = projects.create(self.reg, "Vendors")
        self.items = things("x", "y", "z")

    def test_move_to_sets_main_and_mirrors_the_name_for_older_code(self):
        projects.move_to(self.reg, self.items, ["x", "nope"], self.b)
        self.assertEqual((self.items["x"]["project_id"], self.items["x"]["project"]), (self.b, "Q3 launch"))
        self.assertNotIn("project_id", self.items["y"])

    def test_a_thing_can_be_in_several_projects_with_one_main(self):
        projects.move_to(self.reg, self.items, ["x"], self.b)
        projects.add_also(self.reg, self.items, ["x"], self.c)
        self.assertEqual(self.items["x"]["also_in"], [self.c])
        self.assertEqual([i["id"] for i in projects.members(self.reg, self.items, self.c)], ["x"])
        projects.add_also(self.reg, self.items, ["x"], self.c)              # again: still once
        self.assertEqual(self.items["x"]["also_in"], [self.c])

    def test_add_also_on_a_thing_with_no_project_makes_it_main(self):
        projects.add_also(self.reg, self.items, ["y"], self.c)
        self.assertEqual(self.items["y"]["project_id"], self.c)
        self.assertNotIn("also_in", self.items["y"])

    def test_make_main_keeps_the_old_main_as_also_in(self):
        projects.move_to(self.reg, self.items, ["x"], self.b)
        projects.make_main(self.reg, self.items, ["x"], self.c)
        self.assertEqual((self.items["x"]["project_id"], self.items["x"]["also_in"]), (self.c, [self.b]))
        self.assertEqual(self.items["x"]["project"], "Vendors")

    def test_move_to_drops_the_old_main_and_a_matching_also_in(self):
        projects.move_to(self.reg, self.items, ["x"], self.b)
        projects.add_also(self.reg, self.items, ["x"], self.c)
        projects.move_to(self.reg, self.items, ["x"], self.c)
        self.assertEqual(self.items["x"]["project_id"], self.c)
        self.assertNotIn("also_in", self.items["x"])

    def test_removing_the_main_promotes_the_next_one_and_the_last_leaves_it_unplaced(self):
        projects.move_to(self.reg, self.items, ["x"], self.b)
        projects.add_also(self.reg, self.items, ["x"], self.c)
        projects.remove_from(self.reg, self.items, ["x"], self.b)
        self.assertEqual((self.items["x"]["project_id"], self.items["x"]["project"]), (self.c, "Vendors"))
        projects.remove_from(self.reg, self.items, ["x"], self.c)
        self.assertNotIn("project", self.items["x"])
        self.assertEqual([i["id"] for i in projects.unassigned(self.items)], ["z", "y", "x"])

    def test_not_this_project_is_permanent_until_you_choose_it_again(self):
        projects.move_to(self.reg, self.items, ["x"], self.b)
        projects.not_this(self.reg, self.items, ["x"], self.b)
        self.assertNotIn("project_id", self.items["x"])
        self.assertFalse(projects.allowed(self.items["x"], self.b))        # R14: suggestions must skip it
        self.assertTrue(projects.allowed(self.items["x"], self.c))
        projects.move_to(self.reg, self.items, ["x"], self.b)              # you put it back: lifted
        self.assertTrue(projects.allowed(self.items["x"], self.b))

    def test_members_deep_or_shallow_and_each_thing_once(self):
        projects.move_to(self.reg, self.items, ["x"], self.b)
        projects.add_also(self.reg, self.items, ["x"], self.a)
        projects.move_to(self.reg, self.items, ["y"], self.a)
        deep = projects.members(self.reg, self.items, self.a)
        self.assertEqual(sorted(i["id"] for i in deep), ["x", "y"])
        self.assertEqual([i["id"] for i in projects.members(self.reg, self.items, self.a, deep=False)], ["y", "x"])
        self.assertEqual([i["id"] for i in projects.members(self.reg, self.items, self.b, deep=False)], ["x"])

    def test_counts_roll_up_by_main_project_and_never_twice(self):
        self.items["x"]["notes"] = [{"at": "2026-10-06T10:00:01", "text": "one"}, {"at": "2026-10-06T10:00:02", "text": "two"}]
        projects.move_to(self.reg, self.items, ["x"], self.b)
        projects.add_also(self.reg, self.items, ["x"], self.c)             # also in Vendors: not counted there
        projects.move_to(self.reg, self.items, ["y"], self.a)
        count = projects.counts(self.reg, self.items)
        self.assertEqual((count[self.b]["things"], count[self.b]["open"]), (1, 2))
        self.assertEqual((count[self.a]["things"], count[self.a]["open"]), (2, 2))
        self.assertEqual((count[self.c]["things"], count[self.c]["open"]), (0, 0))
        self.assertEqual(count[self.a]["last"], "2026-10-06T10:01:00")
        self.assertIsNone(count[self.c]["last"])

    def test_finished_notes_do_not_count_as_open(self):
        self.items["x"]["notes"] = [{"at": "2026-10-06T10:00:01", "text": "one"}]
        projects.move_to(self.reg, self.items, ["x"], self.b)
        import notes
        notes.set_done(self.items, [notes.note_id(self.items["x"]["notes"][0])])
        self.assertEqual(projects.counts(self.reg, self.items)[self.b]["open"], 0)


class MergeDeleteTests(unittest.TestCase):
    def setUp(self):
        self.reg = projects.empty()
        self.a = projects.create(self.reg, "Pricing")
        self.a1 = projects.create(self.reg, "India", self.a)
        self.t = projects.create(self.reg, "Plans")
        self.t1 = projects.create(self.reg, "India", self.t)
        self.t2 = projects.create(self.reg, "UK", self.t)
        self.a2 = projects.create(self.reg, "Japan", self.a)
        self.items = things("p", "q", "r", "s")
        projects.move_to(self.reg, self.items, ["p"], self.a)
        projects.move_to(self.reg, self.items, ["q"], self.a1)
        projects.move_to(self.reg, self.items, ["r"], self.t1)
        projects.move_to(self.reg, self.items, ["s"], self.t)
        projects.add_also(self.reg, self.items, ["s"], self.a)

    def test_merge_plan_counts_what_moves_and_refuses_loops(self):
        plan = projects.merge_plan(self.reg, self.items, self.a, self.t)
        self.assertEqual((plan["things"], plan["projects"], plan["into"]), (3, 2, "Plans"))
        with self.assertRaises(ValueError):
            projects.merge_plan(self.reg, self.items, self.a, self.a)
        with self.assertRaises(ValueError):
            projects.merge_plan(self.reg, self.items, self.a, self.a1)

    def test_merge_moves_things_joins_same_named_children_and_keeps_the_old_name(self):
        projects.merge(self.reg, self.items, self.a, self.t)
        self.assertFalse(projects.exists(self.reg, self.a))
        self.assertEqual(self.items["p"]["project_id"], self.t)
        self.assertEqual(self.items["q"]["project_id"], self.t1)         # India joined India
        self.assertFalse(projects.exists(self.reg, self.a1))
        self.assertEqual(projects.get(self.reg, self.a2)["parent"], self.t)   # Japan had no twin: moved
        self.assertEqual(self.items["s"]["project_id"], self.t)
        self.assertNotIn("also_in", self.items["s"])                      # was main + also-in the merged pair
        self.assertEqual(self.items["p"]["project"], "Plans")
        self.assertEqual(projects.find(self.reg, "pricing"), self.t)      # R15: the old name still finds it

    def test_merge_carries_not_this_project_across(self):
        projects.not_this(self.reg, self.items, ["p"], self.a)
        projects.merge(self.reg, self.items, self.a, self.t)
        self.assertFalse(projects.allowed(self.items["p"], self.t))

    def test_delete_keeps_things_unplaced_or_promotes_their_other_project(self):
        out = projects.delete(self.reg, self.items, self.a)
        self.assertEqual((out["projects"], out["things"], out["forget"]), (3, 3, []))
        self.assertNotIn("project", self.items["p"])
        self.assertNotIn("project", self.items["q"])
        self.assertEqual(self.items["s"]["project_id"], self.t)           # its other project took over
        self.assertEqual(sorted(projects.get(self.reg, i)["name"] for i in projects.children(self.reg, None)), ["Plans"])

    def test_delete_and_forget_names_the_things_left_with_no_project(self):
        out = projects.delete(self.reg, self.items, self.a, forget=True)
        self.assertEqual(sorted(out["forget"]), ["p", "q"])

    def test_adopt_turns_old_names_into_projects_once(self):
        items = things("m", "n", "o")
        items["m"]["project"], items["n"]["project"] = "Pricing", "  pricing "
        items["o"]["project_id"] = "p999"                                  # points at nothing
        reg = projects.empty()
        self.assertEqual(projects.adopt(reg, items), 3)
        self.assertEqual(len(reg["projects"]), 1)
        self.assertEqual(items["m"]["project_id"], items["n"]["project_id"])
        self.assertNotIn("project_id", items["o"])
        self.assertEqual(projects.adopt(reg, items), 0)                    # again: nothing to do


class ShowTests(unittest.TestCase):
    def test_resolve_by_path_name_and_alias_and_tree_text(self):
        reg = projects.empty()
        a = projects.create(reg, "Pricing")
        b = projects.create(reg, "Q3 launch", a)
        self.assertEqual(projects.resolve(reg, "pricing / q3 LAUNCH"), b)
        self.assertEqual(projects.resolve(reg, "Pricing › Q3 launch"), b)
        self.assertEqual(projects.resolve(reg, "q3 launch"), b)
        for bad in ("", "Ghost", "Pricing/Ghost"):
            with self.assertRaises(ValueError):
                projects.resolve(reg, bad)
        items = things("x", "y")
        projects.move_to(reg, items, ["x", "y"], b)
        self.assertEqual(projects.tree_lines(reg, items), ["Pricing  · 2 things", "  Q3 launch  · 2 things"])
        projects.archive(reg, b)
        self.assertEqual(projects.tree_lines(reg, items), ["Pricing  · 2 things"])
        self.assertIn("archived", projects.tree_lines(reg, items, include_hidden=True)[1])


class RandomWalkTests(unittest.TestCase):
    def test_no_loops_no_clashes_and_no_double_counting_after_many_random_changes(self):
        for seed in range(30):
            rng = random.Random(seed)
            reg, items = projects.empty(), things(*[f"t{n}" for n in range(12)])
            for step in range(120):
                ids = list(reg["projects"])
                pick = lambda: rng.choice(ids) if ids else None            # noqa: E731
                act = rng.choice("cccmrdgaxnkh")
                try:
                    if act == "c":
                        projects.create(reg, rng.choice("ABCDEF") + str(rng.randint(0, 2)), pick() if ids and rng.random() < .7 else None)
                    elif ids and act == "m":
                        projects.move(reg, pick(), pick() if rng.random() < .8 else None)
                    elif ids and act == "r":
                        projects.rename(reg, pick(), rng.choice("ABCDEF") + str(rng.randint(0, 2)), items)
                    elif ids and act == "d":
                        projects.delete(reg, items, pick(), forget=False)
                    elif ids and act == "g":
                        projects.merge(reg, items, pick(), pick())
                    elif ids and act == "a":
                        projects.move_to(reg, items, [rng.choice(list(items))], pick())
                    elif ids and act == "x":
                        projects.add_also(reg, items, [rng.choice(list(items))], pick())
                    elif ids and act == "n":
                        projects.not_this(reg, items, [rng.choice(list(items))], pick())
                    elif ids and act == "k":
                        projects.make_main(reg, items, [rng.choice(list(items))], pick())
                    elif ids and act == "h":
                        projects.remove_from(reg, items, [rng.choice(list(items))], pick())
                except ValueError:
                    pass
                self.check(reg, items)

    def check(self, reg, items):
        for pid, p in reg["projects"].items():
            if p["parent"] is not None:
                self.assertIn(p["parent"], reg["projects"])
            self.assertEqual(len(projects.ancestors(reg, pid)), len(set(projects.ancestors(reg, pid))))   # no loop
            siblings = [projects.key(reg["projects"][s]["name"]) for s in projects.children(reg, p["parent"])]
            self.assertEqual(len(siblings), len(set(siblings)))                                           # R12
        for it in items.values():
            main = it.get("project_id")
            if main:
                self.assertIn(main, reg["projects"])
                self.assertEqual(it["project"], reg["projects"][main]["name"])
            else:
                self.assertNotIn("project", it)
            also = it.get("also_in", [])
            self.assertEqual(len(also), len(set(also)))
            self.assertNotIn(main, also)
            for p in also:
                self.assertIn(p, reg["projects"])
        total = projects.counts(reg, items)
        tops = [p for p in reg["projects"] if reg["projects"][p]["parent"] is None]
        placed = sum(1 for it in items.values() if it.get("project_id"))
        self.assertEqual(sum(total[t]["things"] for t in tops), placed)                                  # R13


class FileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        ctx = config.use_paths(self.tmp.name)
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)

    def test_a_new_install_has_no_projects_and_saving_round_trips(self):
        self.assertEqual(projects.load()["projects"], {})
        reg = projects.load()
        pid = projects.create(reg, "Pricing")
        projects.create(reg, "Q3", pid)
        projects.save(reg)
        again = projects.load()
        self.assertEqual(projects.path_names(again, projects.find(again, "Q3", pid)), ["Pricing", "Q3"])
        self.assertEqual(projects.create(again, "Next"), "p3")             # ids keep counting up

    def test_a_damaged_file_is_never_replaced_by_an_empty_one(self):
        import os
        os.makedirs(config.paths().memory_dir, exist_ok=True)
        with open(config.paths().projects_file, "w") as fh:
            fh.write("{nope")
        with self.assertRaises(ValueError):
            projects.load()
        with open(config.paths().projects_file, "w") as fh:
            fh.write("[]")
        with self.assertRaises(ValueError):
            projects.load()


if __name__ == "__main__":
    unittest.main()
