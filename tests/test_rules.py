"""The pill's ground rules (rules.py): who owns the screen, and what each press does."""

import unittest
from datetime import datetime

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
        self.assertEqual(rules.hotkey_action(False, False, True), "show_paused")   # R9
        self.assertEqual(rules.hotkey_action(False, True, True), "show_paused")

    def test_clicking_the_pill_while_dictating_does_nothing(self):  # R1
        self.assertEqual(rules.pill_click_action(True), "ignore")
        self.assertEqual(rules.pill_click_action(False), "toggle_card")


class MarkTests(unittest.TestCase):
    def test_marks_strongest_first(self):                           # R8
        ok = {"screen": True, "private": False, "mic_off": False}
        self.assertIsNone(rules.pill_mark(ok))
        self.assertEqual(rules.pill_mark({**ok, "screen": False, "private": True, "mic_off": True}), "screen_off")
        self.assertEqual(rules.pill_mark({**ok, "private": True, "mic_off": True}), "private")
        self.assertEqual(rules.pill_mark({**ok, "mic_off": True}), "mic_off")

    def test_mic_off_gives_way_to_notes_and_suggestions(self):
        mic = {"screen": True, "mic_off": True}
        self.assertIsNone(rules.pill_mark(mic, count=2))
        self.assertIsNone(rules.pill_mark(mic, has_suggestion=True))

    def test_empty_kinds(self):
        fresh = notes.card_view(notes.blank_card("Q3 plan", "Docs"))
        self.assertEqual(rules.empty_kind(fresh), "fresh")
        done = {"title": "Q3", "app": "Docs", "project": "Q3", "left": [], "history": [], "things": 1,
                "visits": 1, "seconds": 1, "plan": [{"id": "a", "text": "x", "at": "t", "on": "Q3", "here": True, "done": "t2"}]}
        self.assertEqual(rules.empty_kind(notes.card_view(done)), "caught")
        done["plan"][0]["done"] = None
        self.assertIsNone(rules.empty_kind(notes.card_view(done)))
        self.assertIsNone(rules.empty_kind(None))
        self.assertIsNone(rules.empty_kind(notes.card_view(None)))

    def test_the_pill_wears_the_mark_but_notes_dictating_and_saving_come_first(self):
        base = dict(note_open=False, saved=False, hover=False, card_open=False, count=0, has_suggestion=False)
        st = lambda **kw: rules.pill_state(**{**base, **kw})
        self.assertEqual(st(mark="private"), "private")
        self.assertEqual(st(mark="private", saved=True), "saved")
        self.assertEqual(st(mark="private", note_open=True), "rest")
        self.assertEqual(st(empty="fresh"), "rest")                 # quiet until you look
        self.assertEqual(st(empty="fresh", hover=True), "fresh")
        self.assertEqual(st(empty="caught", card_open=True), "caught")
        self.assertEqual(st(mark="screen_off", empty="fresh", hover=True), "screen_off")


class PauseTests(unittest.TestCase):
    now = datetime(2026, 10, 9, 14, 40)

    def test_when_each_choice_ends(self):
        self.assertEqual(rules.pause_end("hour", self.now), datetime(2026, 10, 9, 15, 40))
        self.assertEqual(rules.pause_end("tomorrow", self.now), datetime(2026, 10, 10, 8, 0))
        self.assertEqual(rules.pause_end("tomorrow", datetime(2026, 10, 9, 2, 0)), datetime(2026, 10, 9, 8, 0))
        self.assertIsNone(rules.pause_end("until_resume", self.now))

    def test_clock(self):
        self.assertEqual(rules.clock(datetime(2026, 10, 9, 15, 40), self.now), "at 3:40 PM")
        self.assertEqual(rules.clock(datetime(2026, 10, 10, 8, 0), self.now), "tomorrow at 8:00 AM")

    def test_options(self):
        rows = rules.pause_options(self.now)
        self.assertEqual([r["title"] for r in rows], ["1 hour", "Until tomorrow", "Until I resume"])
        self.assertEqual([r["sub"] for r in rows], ["Back on at 3:40 PM", "Back on tomorrow at 8:00 AM", "You turn it back on"])

    def test_paused_cards(self):
        timed = rules.paused_view("manual", datetime(2026, 10, 9, 15, 40), self.now)
        self.assertTrue(timed["resume"])
        self.assertIn("3:40 PM", timed["line"])
        self.assertIn("until you resume", rules.paused_view("manual", None, self.now)["line"])
        away = rules.paused_view("away", None, self.now)
        self.assertFalse(away["resume"])

    def test_one_mark_for_every_pause(self):                        # R9
        ok = {"screen": False, "private": True, "mic_off": True}
        self.assertEqual(rules.pill_mark({**ok, "paused": "manual"}), "paused")
        self.assertEqual(rules.pill_mark({**ok, "paused": "away"}, count=3), "paused")
        self.assertEqual(rules.pill_mark(ok), "screen_off")


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
