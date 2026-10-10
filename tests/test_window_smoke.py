"""window.py draws without Python errors (window_smoke.py, against a fake AppKit, in its own process)."""

import os
import subprocess
import sys
import unittest


class WindowSmokeTests(unittest.TestCase):
    def test_every_page_and_dialog_draws_and_suggestions_are_on_them(self):
        here = os.path.dirname(os.path.abspath(__file__))
        done = subprocess.run([sys.executable, os.path.join(here, "window_smoke.py")], capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
