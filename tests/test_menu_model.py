"""The menu-bar item as data (menu_model.py): one mark, the same words as the pill, Quit always there."""

import unittest
from datetime import datetime

import menu_model
import rules

NOW = datetime(2026, 10, 9, 15, 0)
FINE = {"screen": True, "mic_off": False, "private": False, "unwatched": False, "paused": None}


def status(**changes):
    return {**FINE, **changes}


class ViewTests(unittest.TestCase):
    def test_when_all_is_well_it_says_what_it_is_watching_and_has_no_badge(self):
        v = menu_model.view(FINE)
        self.assertEqual((v["mark"], v["tone"], v["title"], v["line"]), (None, "ok", "LMemM is watching", "Every app"))
        self.assertEqual(v["icon"], {"badge": None, "glyph": None})

    def test_it_names_the_apps_you_chose(self):
        apps = [{"id": "a", "name": "Chrome"}, {"id": "b", "name": "VS Code"}, {"id": "c", "name": "Slack"}]
        self.assertEqual(menu_model.view(FINE, apps)["line"], "Only Chrome, VS Code +1")

    def test_a_permission_that_is_off_is_the_only_red(self):
        for key, title in (("screen", "Screen access is off"), ("mic_off", "Mic is off")):
            v = menu_model.view(status(**{key: key == "mic_off"}))
            self.assertEqual((v["tone"], v["icon"]["badge"], v["title"]), ("red", "red", title))
        for change, mark in (({"private": True}, "private"), ({"unwatched": True}, "unwatched"),
                             ({"paused": "manual"}, "paused"), ({"paused": "away"}, "paused")):
            v = menu_model.view(status(**change, pause_view=rules.paused_view("manual", None, NOW)))
            self.assertEqual((v["mark"], v["tone"], v["icon"]["badge"]), (mark, "grey", "grey"))

    def test_a_pause_shows_two_bars_and_the_pills_own_words(self):
        end = datetime(2026, 10, 9, 15, 40)
        v = menu_model.view(status(paused="manual", pause_view=rules.paused_view("manual", end, NOW)))
        self.assertEqual((v["icon"]["glyph"], v["title"]), ("pause", "Paused"))
        self.assertEqual(v["line"], "Nothing is being remembered. Back on at 3:40 PM.")
        away = menu_model.view(status(paused="away", pause_view=rules.paused_view("away", None, NOW)))
        self.assertIn("stepped away", away["line"])

    def test_the_menu_shows_the_same_single_mark_as_the_pill(self):
        for s in (status(paused="manual"), status(screen=False), status(private=True), status(unwatched=True),
                  status(mic_off=True), status(screen=False, private=True, paused="away"), FINE):
            self.assertEqual(menu_model.view(s)["mark"], rules.pill_mark(s))

    def test_quit_is_always_the_last_row(self):
        for s in (FINE, status(paused="manual"), status(screen=False)):
            rows = menu_model.view(s)["rows"]
            self.assertEqual(rows[-1], {"id": "quit", "title": "Quit LMemM", "key": "q"})

    def test_the_signature_changes_only_when_what_you_see_changes(self):
        a = menu_model.signature(menu_model.view(FINE))
        self.assertEqual(a, menu_model.signature(menu_model.view(status(extra_ignored=1))))
        self.assertNotEqual(a, menu_model.signature(menu_model.view(status(private=True))))
        self.assertNotEqual(a, menu_model.signature(menu_model.view(FINE, [{"id": "a", "name": "Chrome"}])))


if __name__ == "__main__":
    unittest.main()
