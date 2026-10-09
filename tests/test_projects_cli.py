"""`lmemm.py projects` (projects_cli.py): the tree from the terminal. Runs without a Mac."""

import tempfile
import unittest

import config
import projects
import projects_cli
import store


def thing(iid, project=None, last="2026-10-09T10:00:00"):
    d = {"id": iid, "app": "Docs", "doing": "Working", "title": iid, "seconds": 5, "visits": 1,
         "first_seen": "2026-10-09T10:00:00", "last_seen": last, "notes": []}
    if project:
        d["project"] = project
    return d


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        ctx = config.use_paths(self.tmp.name)
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        store.save_memory({"a": thing("a", "Pricing"), "b": thing("b", "Pricing"), "c": thing("c")})
        self.saved = 0

    def run_cli(self, *args, running=False):
        lines = []

        def save(items):
            self.saved += 1
            store.save_memory(items)
        projects_cli.run(list(args), running=running, save_items=save, out=lambda t="": lines.append(t))
        return "\n".join(lines)

    def test_the_tree_adopts_old_project_names_and_counts_what_is_unplaced(self):
        text = self.run_cli()
        self.assertIn("Pricing  · 2 things", text)
        self.assertIn("1 thing not in a project", text)
        self.assertEqual(store.load_items()["a"]["project_id"], projects.find(projects.load(), "Pricing"))

    def test_new_nested_projects_and_paths(self):
        self.run_cli("new", "Q3 launch", "--in", "Pricing")
        self.run_cli("new", "India", "--in", "Pricing/Q3 launch")
        reg = projects.load()
        self.assertEqual(projects.path_names(reg, projects.resolve(reg, "india")), ["Pricing", "Q3 launch", "India"])
        self.assertIn("    India  · 0 things", self.run_cli())

    def test_a_name_used_twice_needs_a_path_unless_one_is_at_the_top(self):
        self.run_cli("new", "Plans")
        self.run_cli("new", "India", "--in", "Pricing")
        self.run_cli("new", "India", "--in", "Plans")
        with self.assertRaises(ValueError) as e:
            self.run_cli("archive", "India")
        self.assertIn("Use the full path", str(e.exception))
        self.run_cli("new", "India")                                  # now one is at the top
        self.assertIn("Archived India", self.run_cli("archive", "India"))
        self.assertIn("Now at Plans/India/India", self.run_cli("move", "India", "--to", "Plans/India"))

    def test_rename_updates_the_things_and_needs_the_tracker_stopped(self):
        self.run_cli()
        with self.assertRaises(ValueError):
            self.run_cli("rename", "Pricing", "Plans", running=True)
        self.run_cli("rename", "Pricing", "Plans")
        self.assertEqual(store.load_items()["a"]["project"], "Plans")

    def test_merge_dry_run_changes_nothing_then_merge_moves_things(self):
        self.run_cli("new", "Plans")
        before = projects.load()
        text = self.run_cli("merge", "Pricing", "--into", "Plans", "--dry-run")
        self.assertIn("2 things", text)
        self.assertEqual(projects.load(), before)
        self.run_cli("merge", "Pricing", "--into", "Plans")
        self.assertEqual(store.load_items()["a"]["project"], "Plans")
        self.assertEqual(projects.resolve(projects.load(), "pricing"), projects.find(projects.load(), "Plans"))

    def test_delete_needs_dry_run_or_confirm_and_forget_removes_the_things(self):
        self.run_cli()
        with self.assertRaises(ValueError):
            self.run_cli("delete", "Pricing")
        self.assertIn("Nothing was changed", self.run_cli("delete", "Pricing", "--dry-run"))
        self.assertIn("Forgot 2", self.run_cli("delete", "Pricing", "--forget", "--confirm"))
        self.assertEqual(sorted(store.load_items()), ["c"])

    def test_archive_hides_it_from_the_tree_until_all(self):
        self.run_cli("archive", "Pricing")
        self.assertIn("No projects yet", self.run_cli())
        self.assertIn("archived", self.run_cli("--all"))
        self.run_cli("restore", "Pricing")
        self.assertIn("Pricing", self.run_cli())

    def test_mistakes_get_a_sentence(self):
        for args, words in (("nope",), "I do not know"), (("rename", "Ghost", "X"), "no project called"), (("new",), "Usage"):
            with self.assertRaises(ValueError) as e:
                self.run_cli(*args)
            self.assertIn(words, str(e.exception))


if __name__ == "__main__":
    unittest.main()
