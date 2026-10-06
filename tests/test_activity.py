import unittest

import activity


def screen(text):
    return {"objects": [{"kind": "text", "text": text, "box": [100, 100, 400, 24]}]}


class ActivityTests(unittest.TestCase):
    def test_input_and_screen_changes_distinguish_activity(self):
        change = {"changed": 0.1, "regions": [[80, 80, 450, 60]], "scroll": 0}
        before = screen("Project choice")
        after = screen("Project choice is SQLite")
        for category, ages, delta in [
            ("typing", {"key": 1, "scroll": 100, "click": 100}, change),
            ("receiving", {"key": 100, "scroll": 100, "click": 100}, change),
            ("focus", {"key": 100, "scroll": 100, "click": 1}, change),
            ("reading", {"key": 100, "scroll": 1, "click": 100}, dict(change, scroll=120)),
        ]:
            with self.subTest(category=category):
                result = activity.classify(delta, before, after, ages, None, 5)
                self.assertEqual(result["category"], category)
                self.assertIn("Project choice is SQLite", result["new_text"])

    def test_arrival_text_is_not_attributed_to_an_activity(self):
        result = activity.classify(None, None, screen("We chose SQLite for this project"),
                                   {"key": 1, "scroll": 1, "click": 1}, None, 0)
        self.assertEqual(result["category"], "reading")
        self.assertEqual(result["new_text"], [])


if __name__ == "__main__":
    unittest.main()
