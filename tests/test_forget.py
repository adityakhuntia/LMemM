"""delete-all (forget.py): everything inside LMemM's data directory, and nothing else."""

import os
import tempfile
import unittest

import forget


class ForgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "lmemm", "data")
        os.makedirs(os.path.join(self.root, "memory", "sessions"))
        for rel in ("20261009-101010.jpg", "20261009-101010.json", "onboarding.json",
                    "memory/memory.json", "memory/sessions/s1.json"):
            with open(os.path.join(self.root, rel), "w") as fh:
                fh.write("x" * 10)
        self.outside = os.path.join(self.tmp.name, "keep.txt")
        with open(self.outside, "w") as fh:
            fh.write("mine")

    def test_dry_run_changes_nothing(self):
        plan = forget.plan(self.root)
        self.assertEqual((plan["files"], plan["bytes"]), (5, 50))
        self.assertEqual(plan["entries"], ["20261009-101010.jpg", "20261009-101010.json", "memory", "onboarding.json"])
        self.assertTrue(os.path.exists(os.path.join(self.root, "memory", "memory.json")))

    def test_delete_all_empties_the_folder_and_keeps_the_folder(self):
        done = forget.delete_all(self.root)
        self.assertEqual(done["files"], 5)
        self.assertEqual(os.listdir(self.root), [])
        self.assertTrue(os.path.isdir(self.root))
        self.assertTrue(os.path.exists(self.outside))

    def test_deleting_twice_is_fine(self):
        forget.delete_all(self.root)
        self.assertEqual(forget.delete_all(self.root)["files"], 0)

    def test_it_refuses_while_lmemm_is_running(self):
        with self.assertRaises(ValueError) as caught:
            forget.delete_all(self.root, running_pid=4242)
        self.assertIn("4242", str(caught.exception))
        self.assertTrue(os.path.exists(os.path.join(self.root, "onboarding.json")))

    def test_it_refuses_directories_that_are_not_lmemms(self):
        for bad in ("/", os.path.expanduser("~"), os.path.join(self.tmp.name, "nope"), self.outside, "/tmp"):
            with self.assertRaises(ValueError, msg=bad):
                forget.delete_all(bad)
        self.assertTrue(os.path.exists(self.outside))

    def test_a_link_inside_the_folder_is_removed_but_not_followed(self):
        target = os.path.join(self.tmp.name, "elsewhere")
        os.makedirs(target)
        with open(os.path.join(target, "precious"), "w") as fh:
            fh.write("keep")
        os.symlink(target, os.path.join(self.root, "link"))
        forget.delete_all(self.root)
        self.assertFalse(os.path.lexists(os.path.join(self.root, "link")))
        self.assertTrue(os.path.exists(os.path.join(target, "precious")))


if __name__ == "__main__":
    unittest.main()
