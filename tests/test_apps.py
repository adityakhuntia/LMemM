"""Which apps LMemM may look at (apps.py): the rule, the clean-up, and the installed-app scan."""

import os
import plistlib
import tempfile
import unittest

import apps

CHROME = {"id": "com.google.Chrome", "name": "Chrome"}
CODE = {"id": "com.microsoft.VSCode", "name": "VS Code"}


class WatchedTests(unittest.TestCase):
    def test_an_empty_list_watches_every_app(self):                       # S5
        for empty in (None, [], (), "", {}):
            for bundle in ("com.apple.Safari", None, ""):
                self.assertTrue(apps.watched(empty, bundle), (empty, bundle))

    def test_a_list_watches_only_those_apps(self):                         # R11
        self.assertTrue(apps.watched([CHROME, CODE], "com.google.Chrome"))
        self.assertTrue(apps.watched([CHROME, CODE], "com.microsoft.VSCode"))
        self.assertFalse(apps.watched([CHROME, CODE], "com.apple.Safari"))
        self.assertFalse(apps.watched([CHROME], "com.google.Chrome.canary"))   # exact match, not a prefix

    def test_an_app_that_cannot_be_identified_is_not_watched(self):        # fails closed
        self.assertFalse(apps.watched([CHROME], None))
        self.assertFalse(apps.watched([CHROME], ""))

    def test_bare_ids_work_too(self):
        self.assertTrue(apps.watched(["com.google.Chrome"], "com.google.Chrome"))

    def test_a_list_of_nothing_usable_is_no_limit_at_all(self):
        self.assertTrue(apps.watched([{"id": ""}, None, 3, {"name": "x"}], "anything"))


class CleanTests(unittest.TestCase):
    def test_clean(self):
        got = apps.clean([CHROME, {"id": "com.google.Chrome", "name": "Dup"}, {"id": " "}, None, 3,
                          {"id": "bare"}, "str.id", {"id": "n", "name": "x" * 500}])
        self.assertEqual([e["id"] for e in got], ["com.google.Chrome", "bare", "str.id", "n"])
        self.assertEqual(got[0]["name"], "Chrome")                       # first wins
        self.assertEqual(got[1]["name"], "bare")                          # no name: the id stands in
        self.assertEqual(len(got[3]["name"]), 80)

    def test_clean_never_raises_and_is_bounded(self):
        for junk in (None, 5, "x", {"a": 1}, object()):
            self.assertEqual(apps.clean(junk), [])
        many = [{"id": f"app.{i}", "name": "n"} for i in range(apps.MAX_WATCHED + 50)]
        self.assertEqual(len(apps.clean(many)), apps.MAX_WATCHED)

    def test_clean_is_idempotent(self):
        once = apps.clean([CHROME, CODE, "x"])
        self.assertEqual(apps.clean(once), once)

    def test_describe(self):
        self.assertIsNone(apps.describe([]))
        self.assertIsNone(apps.describe(None))
        self.assertEqual(apps.describe([CHROME]), "Only Chrome")
        self.assertEqual(apps.describe([CHROME, CODE]), "Only Chrome, VS Code")
        self.assertEqual(apps.describe([CHROME, CODE, {"id": "c", "name": "Notes"}, {"id": "d", "name": "Mail"}]),
                         "Only Chrome, VS Code +2")


class InstalledTests(unittest.TestCase):
    def make(self, root, folder, **plist):
        contents = os.path.join(root, folder, "Contents")
        os.makedirs(contents)
        if plist:
            with open(os.path.join(contents, "Info.plist"), "wb") as fh:
                plistlib.dump(plist, fh)

    def test_lists_real_apps_sorted_and_leaves_out_the_rest(self):
        with tempfile.TemporaryDirectory() as root:
            self.make(root, "Zed.app", CFBundleIdentifier="dev.zed", CFBundleName="Zed")
            self.make(root, "Chrome.app", CFBundleIdentifier="com.google.Chrome", CFBundleDisplayName="Google Chrome",
                      CFBundleName="Chrome")
            self.make(root, "NoName.app", CFBundleIdentifier="com.example.noname")
            self.make(root, "Agent.app", CFBundleIdentifier="com.example.agent", LSUIElement=True)
            self.make(root, "Daemon.app", CFBundleIdentifier="com.example.daemon", LSBackgroundOnly=True)
            self.make(root, "Listen.app", CFBundleIdentifier="com.lmemm.listen", CFBundleName="LMemM Listen")
            self.make(root, "Broken.app")                                  # no Info.plist
            self.make(root, "NoId.app", CFBundleName="No id")
            with open(os.path.join(root, "notes.txt"), "w") as fh:
                fh.write("not an app")
            os.makedirs(os.path.join(root, "Folder"))
            listing = apps.installed([root])
        self.assertEqual([a["name"] for a in listing], ["Google Chrome", "NoName", "Zed"])
        self.assertEqual(listing[0]["id"], "com.google.Chrome")
        self.assertTrue(listing[0]["path"].endswith("Chrome.app"))

    def test_the_same_app_in_two_folders_is_listed_once_and_a_missing_folder_is_fine(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.make(a, "X.app", CFBundleIdentifier="x.app", CFBundleName="X")
            self.make(b, "X Copy.app", CFBundleIdentifier="x.app", CFBundleName="X")
            self.assertEqual(len(apps.installed([a, b, "/no/such/folder"])), 1)

    def test_a_corrupt_plist_is_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            self.make(root, "Bad.app")
            with open(os.path.join(root, "Bad.app", "Contents", "Info.plist"), "wb") as fh:
                fh.write(b"\x00\x01 not a plist")
            self.make(root, "Good.app", CFBundleIdentifier="good", CFBundleName="Good")
            self.assertEqual([a["id"] for a in apps.installed([root])], ["good"])

    def test_search(self):
        listing = [{"id": "1", "name": "Google Chrome"}, {"id": "2", "name": "Chromium"}, {"id": "3", "name": "Notes"}]
        self.assertEqual([a["id"] for a in apps.search(listing, "chrom")], ["1", "2"])
        self.assertEqual([a["id"] for a in apps.search(listing, "  NOTES ")], ["3"])
        self.assertEqual(len(apps.search(listing, "")), 3)
        self.assertEqual(len(apps.search(listing, None)), 3)
        self.assertEqual(apps.search(listing, "zzz"), [])


if __name__ == "__main__":
    unittest.main()
