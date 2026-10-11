"""runs.py: one data folder per run, named #PR<number>|<date>|Session <n>; shared setup and token count."""

import json
import os
import unittest
from datetime import datetime

import config
import labels
import runs
from test_labels import TmpPaths

DAY1, DAY2 = datetime(2026, 10, 12, 9, 0, 0), datetime(2026, 10, 13, 9, 0, 0)


class RunTests(TmpPaths):
    def test_sessions_count_up_per_pr_and_day(self):
        base = config.paths().data_dir
        names = []
        for now in (DAY1, DAY1, DAY2):
            names.append(os.path.basename(runs.begin("25", now)))
        self.assertEqual(names, ["#PR25|2026-10-12|Session 1", "#PR25|2026-10-12|Session 2", "#PR25|2026-10-13|Session 1"])
        self.assertTrue(os.path.isdir(os.path.join(base, "runs", names[0])))

    def test_a_new_run_has_its_own_memory_but_keeps_the_user_and_the_token_count(self):
        base = config.paths().data_dir
        os.makedirs(os.path.join(base, "memory"))
        with open(os.path.join(base, "memory", "memory.json"), "w") as fh:
            json.dump({"things": [{"x": 1}], "items": [{"id": "old"}], "user": {"name": "Ada"}}, fh)
        first = runs.begin("25", DAY1)
        labels.Governor().record({"input_tokens": 100, "output_tokens": 50})
        with open(os.path.join(first, "memory", "memory.json")) as fh:
            doc = json.load(fh)
        self.assertEqual((doc["user"], doc["items"]), ({"name": "Ada"}, []))          # the old garbled things do not come along
        config.PATHS = config.PATHS.__class__(**{**config.PATHS.__dict__, "data_dir": base, "base_dir": None})
        second = runs.begin("25", DAY1)
        self.assertNotEqual(first, second)
        self.assertEqual(labels.Governor().used, 150)                                # one daily count across runs
        self.assertEqual(config.paths().onboarding_file, os.path.join(base, "onboarding.json"))
        self.assertTrue(config.paths().items_file.startswith(second))

    def test_reading_commands_follow_the_latest_run_or_the_one_named(self):
        base = config.paths().data_dir
        a, b = runs.begin("25", DAY1), runs.begin("25", DAY2)
        self.assertEqual(runs.latest(base), b)
        args = ["--run", "10-12|Session 1", "extra"]
        folder = runs.select(args)
        self.assertEqual((folder, args), (a, ["extra"]))
        self.assertEqual(runs.select([]), b)
        with self.assertRaises(ValueError):
            runs.select(["--run", "PR99"])

    def test_the_pr_number_comes_from_the_flag_first(self):
        self.assertEqual(runs.pr_number("#PR25"), "25")
        os.environ["LMEMM_PR"] = "31"
        self.addCleanup(os.environ.pop, "LMEMM_PR", None)
        self.assertEqual(runs.pr_number(None), "31")


if __name__ == "__main__":
    unittest.main()
