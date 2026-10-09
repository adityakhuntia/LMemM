"""The pill's ground rules (rules.py): who owns the screen, and what each press does."""

import unittest

import notes
import rules


class OwnershipTests(unittest.TestCase):
    def state(self, **kw):
        base = dict(note_open=False, saved=False, hover=False, card_open=False, count=0, has_suggestion=False)
        return rules.pill_state(**{**base, **kw})

    def test_the_note_card_silences_everything_else(self):          # R1
        self.assertEqual(self.state(note_open=True, saved=True, hover=True, count=3, has_suggestion=True), "rest")

    def test_order_after_the_note_card(self):
        self.assertEqual(self.state(saved=True, hover=True, count=2), "saved")
        self.assertEqual(self.state(hover=True, count=2), "peek")
        self.assertEqual(self.state(hover=True, card_open=True, count=2), "count")
        self.assertEqual(self.state(has_suggestion=True), "suggest")
        self.assertEqual(self.state(count=1, has_suggestion=True), "count")
        self.assertEqual(self.state(), "rest")

    def test_hotkey(self):                                          # R2, R3, R6
        self.assertEqual(rules.hotkey_action(False, False, False), "open_note")
        self.assertEqual(rules.hotkey_action(False, True, False), "close_card_then_open_note")
        self.assertEqual(rules.hotkey_action(True, False, False), "ignore")
        self.assertEqual(rules.hotkey_action(True, True, False), "ignore")
        self.assertEqual(rules.hotkey_action(False, False, True), "ignore")

    def test_clicking_the_pill_while_dictating_does_nothing(self):  # R1
        self.assertEqual(rules.pill_click_action(True), "ignore")
        self.assertEqual(rules.pill_click_action(False), "toggle_card")


class PendingTests(unittest.TestCase):
    blank = staticmethod(lambda: notes.blank_card("Safari", "Safari"))

    def test_a_note_still_waiting_counts_here_at_once(self):       # R4
        card = rules.with_pending(None, [{"text": "add pricing", "at": "t1"}], self.blank)
        self.assertEqual(notes.pill_summary(card), (1, "add pricing"))
        view = notes.card_view(card)
        self.assertFalse(view.get("empty"))

    def test_waiting_notes_join_the_real_ones(self):
        base = {"title": "Q3", "app": "Docs", "project": "Q3", "left": [
            {"id": "a", "text": "old", "at": "t0", "on": "Q3", "here": True, "done": None}],
            "plan": [], "history": [], "things": 1, "visits": 1, "seconds": 1}
        card = rules.with_pending(base, [{"text": "new", "at": "t1"}], self.blank)
        self.assertEqual([r["text"] for r in card["left"]], ["new", "old"])
        self.assertEqual(len(base["left"]), 1)                      # the original is untouched

    def test_nothing_waiting_changes_nothing(self):
        self.assertIsNone(rules.with_pending(None, [], self.blank))


if __name__ == "__main__":
    unittest.main()
