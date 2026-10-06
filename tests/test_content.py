import unittest

from memory_content import extract_content, remember_content, visible_window_region


def observation(text="We chose SQLite because the data stays local.", **changes):
    meta = {"iso": "2026-10-04T09:00:00", "app": "Notes", "window": "Project plan",
            "url": None, "window_region": [0.2, 0.1, 0.6, 0.8]}
    meta.update(changes)
    res = {"image_size": {"w": 1000, "h": 800}, "objects": [
        {"kind": "paragraph", "text": text, "conf": 0.99, "box": [250, 200, 450, 30]},
        {"kind": "paragraph", "text": "We decided to leak an unrelated window.",
         "conf": 0.99, "box": [0, 740, 600, 20]},
        {"kind": "sidebar_item", "text": "Unrelated sidebar navigation content", "conf": 1,
         "box": [220, 300, 400, 20]},
    ]}
    return res, meta


class ContentTests(unittest.TestCase):
    def test_keeps_visible_content_and_attributed_decision_quote(self):
        res, meta = observation()
        capture = extract_content(res, meta)
        self.assertEqual(capture["text"], "We chose SQLite because the data stays local.")
        self.assertEqual(capture["decision_quotes"], [capture["text"]])
        self.assertEqual(capture["source"]["window"], "Project plan")
        self.assertEqual(capture["observed_at"], "2026-10-04T09:00:00")

    def test_unknown_window_geometry_does_not_attribute_whole_display(self):
        res, meta = observation()
        del meta["window_region"]
        self.assertIsNone(extract_content(res, meta))

    def test_question_is_not_a_decision_quote(self):
        res, meta = observation("Should we choose SQLite for this project?")
        self.assertEqual(extract_content(res, meta)["decision_quotes"], [])

    def test_repeats_update_time_and_changes_preserve_earlier_content(self):
        item = {}
        first = extract_content(*observation())
        self.assertTrue(remember_content(item, first))
        repeated = extract_content(*observation(iso="2026-10-04T09:00:05"))
        self.assertFalse(remember_content(item, repeated))
        self.assertEqual(len(item["content"]["excerpts"]), 1)
        excerpt = item["content"]["excerpts"][0]
        self.assertEqual(excerpt["first_seen"], "2026-10-04T09:00:00")
        self.assertEqual(excerpt["last_seen"], "2026-10-04T09:00:05")
        changed = extract_content(*observation("We decided to use PostgreSQL for shared access."))
        self.assertTrue(remember_content(item, changed))
        self.assertEqual(len(item["content"]["excerpts"]), 2)
        self.assertIn("SQLite", item["content"]["excerpts"][0]["text"])
        # Returning to previously seen text must also refresh the screenshot.
        self.assertTrue(remember_content(item, repeated))
        self.assertIn("SQLite", item["content"]["excerpts"][-1]["text"])
        self.assertFalse(remember_content(item, None))
        self.assertEqual(len(item["content"]["excerpts"]), 2)

    def test_content_history_and_excerpt_size_are_bounded(self):
        item = {}
        for n in range(30):
            capture = extract_content(*observation(f"Observation {n}: " + "useful project context " * 400))
            remember_content(item, capture)
        excerpts = item["content"]["excerpts"]
        self.assertLessEqual(len(excerpts), 12)
        self.assertTrue(all(len(e["text"]) <= 3000 for e in excerpts))
        self.assertTrue(excerpts[-1]["text"].startswith("Observation 29:"))

    def test_window_region_clips_to_display_and_handles_second_monitor(self):
        self.assertEqual(visible_window_region(
            {"X": 900, "Y": 0, "Width": 500, "Height": 800},
            {"X": 1000, "Y": 0, "Width": 1000, "Height": 800}), [0, 0, 0.4, 1])
        self.assertIsNone(visible_window_region(None, {}))


if __name__ == "__main__":
    unittest.main()
