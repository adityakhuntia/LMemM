"""The only-some-apps gate (R11) must come before anything is read or grabbed from an app.

The tracker needs a Mac to import, so this reads its source: in capture() and identify_now(),
the apps.watched() check has to come before the first call that looks at the app or the screen.
"""

import ast
import os
import unittest

SRC = os.path.join(os.path.dirname(__file__), "..", "src", "tracker.py")
LOOKS = {"browser_info", "browser_info_cached", "grab", "grab_with_screencapture", "start_read", "display_for", "input_ages"}


def calls_in(func):
    out = []
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None
            owner = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else None
            out.append((node.lineno, owner, name))
    return sorted(out, key=lambda c: c[0])


class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SRC) as fh:
            tree = ast.parse(fh.read())
        cls.methods = {n.name: n for c in tree.body if isinstance(c, ast.ClassDef) for n in c.body
                       if isinstance(n, ast.FunctionDef)}

    def check(self, name):
        calls = calls_in(self.methods[name])
        gate = [line for line, owner, call in calls if (owner, call) == ("apps", "watched")]
        self.assertTrue(gate, f"{name}() never checks apps.watched")
        looks = [line for line, owner, call in calls if call in LOOKS]
        self.assertTrue(looks, f"{name}() no longer looks at anything; update this test")
        self.assertLess(min(gate), min(looks), f"{name}() reads the app before the R11 check")

    def test_capture_checks_before_it_reads_or_grabs(self):
        self.check("_capture")

    def test_identify_now_checks_before_it_reads(self):
        self.check("identify_now")

    def test_the_hotkey_path_knows_about_unwatched_apps(self):
        tick = calls_in(self.methods["tick"])
        self.assertTrue(any(owner == "apps" and name == "watched" for _l, owner, name in tick))

    def test_the_status_reports_unwatched_to_the_pill(self):
        with open(SRC) as fh:
            source = fh.read()
        self.assertIn('"unwatched": self.skip_kind == "unwatched"', source)


if __name__ == "__main__":
    unittest.main()
