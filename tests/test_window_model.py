"""The window's banner as data (window_model.py): one state, the pill's words, at most one button."""

import unittest
from datetime import datetime

import menu_model
import rules
import window_model as wm

NOW = datetime(2026, 10, 9, 15, 0)
FINE = {"screen": True, "mic_off": False, "private": False, "unwatched": False, "paused": None}


def status(**changes):
    return {**FINE, **changes}


def paused(kind="manual"):
    return status(paused=kind, pause_view=rules.paused_view(kind, None, NOW))


class BannerTests(unittest.TestCase):
    def test_when_all_is_well_there_is_no_banner_and_it_says_what_it_watches(self):
        v = wm.view(FINE)
        self.assertIsNone(v["banner"])
        self.assertEqual((v["heading"], v["line"]), ("LMemM", "Watching: Every app"))
        apps = [{"id": "a", "name": "Chrome"}, {"id": "b", "name": "VS Code"}]
        self.assertEqual(wm.view(FINE, watch_apps=apps)["line"], "Watching: Only Chrome, VS Code")

    def test_every_state_has_one_banner_with_the_menus_words(self):
        for s in (paused(), paused("away"), status(screen=False), status(screen=False, restart=True),
                  status(mic_off=True), status(private=True), status(unwatched=True)):
            b = wm.banner(s)
            _, title, line = menu_model.status_words(s)
            self.assertEqual((b["title"], b["line"]), (title, line))

    def test_the_states_the_pill_never_has(self):
        for memory, tone, button in (("loading", "calm", None), ("first_run", "calm", "Finish setup"),
                                     ("damaged", "red", "Show the file")):
            b = wm.banner(FINE, memory)
            self.assertEqual((b["kind"], b["tone"], b["button"] and b["button"]["title"]), (memory, tone, button))

    def test_red_is_only_a_permission_that_is_off_or_an_unreadable_file(self):
        red = {k for k, s in {"screen": status(screen=False), "mic": status(mic_off=True),
                              "damaged": FINE}.items() if wm.banner(s, "damaged" if k == "damaged" else "ok")["tone"] == "red"}
        self.assertEqual(red, {"screen", "mic", "damaged"})
        for s in (paused(), paused("away"), status(private=True), status(unwatched=True),
                  status(screen=False, restart=True)):
            self.assertEqual(wm.banner(s)["tone"], "grey")
        for memory in ("loading", "first_run"):
            self.assertEqual(wm.banner(FINE, memory)["tone"], "calm")

    def test_the_strongest_state_wins_and_there_is_only_ever_one(self):
        self.assertEqual(wm.banner(status(screen=False, mic_off=True, private=True), "damaged")["kind"], "damaged")
        self.assertEqual(wm.banner(paused(), "first_run")["kind"], "first_run")
        self.assertEqual(wm.banner(status(screen=False, private=True))["kind"], "screen_off")
        self.assertEqual(wm.banner(status(paused="manual", screen=False, pause_view=rules.paused_view("manual", None, NOW)))["kind"], "paused:manual")

    def test_buttons(self):
        def button(s, memory="ok"):
            b = wm.banner(s, memory)["button"]
            return b and (b["title"], b["id"])
        self.assertEqual(button(paused()), ("Resume", "resume"))
        self.assertIsNone(button(paused("away")))                      # resumes by itself: nothing to do
        self.assertEqual(button(status(screen=False)), ("Open System Settings", "access"))
        self.assertEqual(button(status(screen=False, restart=True)), ("Restart LMemM", "restart"))
        self.assertEqual(button(status(mic_off=True)), ("Open System Settings", "access"))
        self.assertIsNone(button(status(private=True)))
        self.assertIsNone(button(status(unwatched=True)))
        self.assertEqual(button(FINE, "damaged"), ("Show the file", "show_file"))

    def test_a_button_always_does_what_the_menu_row_with_the_same_id_does(self):
        known = {r["id"] for r in menu_model.rows_for(status(screen=False, restart=True), NOW)} | {"show_file", "access"}
        for s, memory in ((paused(), "ok"), (status(screen=False), "ok"), (status(screen=False, restart=True), "ok"),
                          (status(mic_off=True), "ok"), (FINE, "first_run"), (FINE, "damaged")):
            b = wm.banner(s, memory)["button"]
            self.assertIn(b["id"], known | {"resume", "setup"}, b)

    def test_the_signature_changes_only_when_the_window_would(self):
        a = wm.signature(wm.view(FINE))
        self.assertEqual(a, wm.signature(wm.view(FINE)))
        self.assertNotEqual(a, wm.signature(wm.view(status(mic_off=True))))
        self.assertNotEqual(wm.signature(wm.view(paused())), wm.signature(wm.view(paused("away"))))

    def test_the_tracker_answers_every_button_the_window_can_send(self):
        import ast
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "src", "tracker.py")
        with open(path) as fh:
            tree = ast.parse(fh.read())
        fn = next(n for c in tree.body if isinstance(c, ast.ClassDef) for n in c.body
                  if isinstance(n, ast.FunctionDef) and n.name == "menu_pick")
        text = ast.unparse(fn)
        for _title, row in wm.ACTIONS.values():
            self.assertIn(repr(row), text, row)


if __name__ == "__main__":
    unittest.main()
