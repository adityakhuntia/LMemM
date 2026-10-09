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

    def test_pause_is_a_plain_row_with_the_pills_three_choices(self):
        rows = menu_model.view(FINE, now=NOW)["rows"]
        self.assertEqual([r["id"] for r in rows], ["pause", "-", "quit"])
        pause = rows[0]
        self.assertEqual(pause["title"], "Pause LMemM")
        self.assertEqual([c["id"] for c in pause["children"]], ["pause:hour", "pause:tomorrow", "pause:until_resume"])
        self.assertEqual([c["title"] for c in pause["children"]], ["1 hour", "Until tomorrow", "Until I resume"])
        self.assertEqual(pause["children"][0]["detail"], "Back on at 4:00 PM")
        self.assertEqual(pause["children"][1]["detail"], "Back on tomorrow at 8:00 AM")
        self.assertEqual(pause["children"][2]["detail"], "You turn it back on")

    def test_the_menu_offers_what_the_pill_offers(self):
        pill = [(o["kind"], o["title"], o["sub"]) for o in rules.pause_options(NOW)]
        menu = [(menu_model.pause_kind(c["id"]), c["title"], c["detail"])
                for c in menu_model.view(FINE, now=NOW)["rows"][0]["children"]]
        self.assertEqual(menu, pill)

    def test_a_pause_you_chose_has_resume_and_an_automatic_one_has_nothing_to_do(self):
        mine = menu_model.view(status(paused="manual"), now=NOW)["rows"]
        self.assertEqual([r["id"] for r in mine], ["resume", "-", "quit"])
        away = menu_model.view(status(paused="away"), now=NOW)["rows"]
        self.assertEqual([r["id"] for r in away], ["quit"])

    def test_every_clickable_row_id_is_one_the_tracker_understands(self):
        known = {"resume", "quit"} | {"pause:" + k for k in rules.PAUSE_CHOICES}
        for s in (FINE, status(paused="manual"), status(paused="away"), status(screen=False)):
            for row in menu_model.view(s, now=NOW)["rows"]:
                for r in [row] + row.get("children", []):
                    if r["id"] not in {"-", "pause"}:
                        self.assertIn(r["id"], known)
        self.assertIsNone(menu_model.pause_kind("pause:forever"))
        self.assertIsNone(menu_model.pause_kind("quit"))
        self.assertEqual(menu_model.pause_kind("pause:tomorrow"), "tomorrow")

    def test_the_signature_changes_only_when_what_you_see_changes(self):
        a = menu_model.signature(menu_model.view(FINE, now=NOW))
        self.assertEqual(a, menu_model.signature(menu_model.view(status(extra_ignored=1), now=NOW)))
        self.assertNotEqual(a, menu_model.signature(menu_model.view(status(private=True), now=NOW)))
        self.assertNotEqual(a, menu_model.signature(menu_model.view(FINE, [{"id": "a", "name": "Chrome"}], now=NOW)))


class TrackerWiringTests(unittest.TestCase):
    """The tracker needs a Mac to import, so its handler is checked from the source."""

    def test_the_tracker_answers_every_row_the_menu_can_send(self):
        import ast
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "src", "tracker.py")
        with open(path) as fh:
            tree = ast.parse(fh.read())
        fn = next(n for c in tree.body if isinstance(c, ast.ClassDef) for n in c.body
                  if isinstance(n, ast.FunctionDef) and n.name == "menu_pick")
        called = {n.func.attr for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertTrue({"pause_kind", "widget_pause", "widget_resume"} <= called)
        text = ast.unparse(fn)
        self.assertIn("'resume'", text)
        self.assertIn("quit_requested", text)


if __name__ == "__main__":
    unittest.main()
