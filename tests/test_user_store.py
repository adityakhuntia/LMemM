"""The "user" block of memory.json (store.py): written by setup, kept by the tracker's saves."""

import json
import os
import tempfile
import unittest

import config
import store

USER = {"name": "Ada", "works_on": ["code"], "set_up": "2026-10-09", "onboarding": 1}


class UserStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        ctx = config.use_paths(self.tmp.name)
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        self.file = config.paths().items_file

    def read(self):
        with open(self.file) as fh:
            return json.load(fh)

    def test_no_user_until_setup(self):
        self.assertIsNone(store.load_user())
        self.assertEqual(store.load_items(), {})

    def test_save_user_creates_a_valid_memory_file(self):
        store.save_user(USER)
        doc = self.read()
        self.assertEqual(doc["user"], USER)
        self.assertEqual((doc["things"], doc["items"], doc["schema_version"]), ([], [], store.SCHEMA))
        self.assertEqual(store.load_items(), {})                       # the rest of the app still reads it
        self.assertEqual(store.load_user(), USER)

    def test_save_user_leaves_everything_else_alone(self):
        item = {"id": "doc-1", "app": "Docs", "doing": "Working", "title": "Q3", "seconds": 5, "visits": 1,
                "first_seen": "2026-10-09T10:00:00", "last_seen": "2026-10-09T10:01:00", "notes": []}
        store.save_memory({"doc-1": item})
        before = self.read()
        store.save_user(USER)
        after = self.read()
        self.assertEqual(after["user"], USER)
        for key in ("items", "things", "schema_version", "updated"):
            self.assertEqual(after[key], before[key], key)

    def test_the_tracker_saving_memory_keeps_the_user(self):
        store.save_user(USER)
        item = {"id": "doc-1", "app": "Docs", "doing": "Working", "title": "Q3", "seconds": 5, "visits": 1,
                "first_seen": "2026-10-09T10:00:00", "last_seen": "2026-10-09T10:01:00", "notes": []}
        store.save_memory({"doc-1": item})
        store.save_memory({"doc-1": item})
        self.assertEqual(self.read()["user"], USER)
        self.assertEqual(list(store.load_items()), ["doc-1"])

    def test_a_memory_file_without_a_user_stays_without_one(self):
        store.save_memory({})
        self.assertNotIn("user", self.read())

    def test_a_damaged_memory_file_is_never_overwritten(self):
        os.makedirs(os.path.dirname(self.file))
        for text in ("{not json", "[1, 2]", '"x"'):
            with open(self.file, "w") as fh:
                fh.write(text)
            with self.assertRaises(ValueError):
                store.save_user(USER)
            with open(self.file) as fh:
                self.assertEqual(fh.read(), text)

    def test_only_an_object_can_be_saved(self):
        for bad in (None, [], "x", 5):
            with self.assertRaises(ValueError):
                store.save_user(bad)

    def test_the_cache_follows_the_data_directory(self):
        store.save_user(USER)
        with tempfile.TemporaryDirectory() as other, config.use_paths(other):
            self.assertIsNone(store.load_user())
            store.save_user({"name": "Bob"})
            self.assertEqual(store.load_user(), {"name": "Bob"})
        self.assertEqual(store.load_user(), USER)

    def test_a_user_block_that_is_not_an_object_is_ignored(self):
        os.makedirs(os.path.dirname(self.file))
        with open(self.file, "w") as fh:
            json.dump({"schema_version": store.SCHEMA, "user": "Ada", "things": [], "items": []}, fh)
        self.assertIsNone(store.load_user())

    def test_a_legacy_file_without_items_is_not_emptied(self):
        os.makedirs(os.path.dirname(self.file))
        legacy = {"schema_version": 2, "things": [{"id": "a"}]}
        with open(self.file, "w") as fh:
            json.dump(legacy, fh)
        store.save_user(USER)
        self.assertEqual(self.read(), {**legacy, "user": USER})


if __name__ == "__main__":
    unittest.main()
