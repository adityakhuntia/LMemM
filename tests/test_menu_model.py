"""The menu-bar item as data (menu_model.py): one mark, the same words as the pill, Quit always there."""

import unittest
from datetime import datetime

import menu_model
import rules

NOW = datetime(2026, 10, 9, 15, 0)
FINE = {"screen": True, "mic_off": False, "private": False, "unwatched": False, "paused": None}


def ids(rows):
    return [r["id"] for r in rows]


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
        pause = next(r for r in rows if r["id"] == "pause")
        self.assertEqual(pause["title"], "Pause LMemM")
        self.assertEqual([c["id"] for c in pause["children"]], ["pause:hour", "pause:tomorrow", "pause:until_resume"])
        self.assertEqual([c["title"] for c in pause["children"]], ["1 hour", "Until tomorrow", "Until I resume"])
        self.assertEqual(pause["children"][0]["detail"], "Back on at 4:00 PM")
        self.assertEqual(pause["children"][1]["detail"], "Back on tomorrow at 8:00 AM")
        self.assertEqual(pause["children"][2]["detail"], "You turn it back on")

    def test_the_rows_in_order_with_no_dead_rows(self):
        self.assertEqual(ids(menu_model.view(FINE, now=NOW)["rows"]),
                         ["add_note", "-", "pause", "-", "access", "setup", "-", "delete", "quit"])
        titles = [r["title"] for r in menu_model.view(FINE, now=NOW)["rows"] if r["id"] != "-"]
        self.assertEqual(titles, ["Add a note", "Pause LMemM", "Check access…", "Reopen setup…",
                                  "Delete all my data…", "Quit LMemM"])
        self.assertNotIn("Open project page", titles)              # there is no project page yet

    def test_dividers_never_start_end_or_double_up(self):
        for s in (FINE, status(paused="manual"), status(paused="away"), status(screen=False),
                  status(screen=False, restart=True), status(mic_off=True)):
            rows = ids(menu_model.view(s, now=NOW)["rows"])
            self.assertNotEqual((rows[0], rows[-1]), ("-", "-"))
            self.assertNotEqual(rows[0], "-")
            self.assertNotEqual(rows[-1], "-")
            self.assertFalse(any(a == b == "-" for a, b in zip(rows, rows[1:])), rows)

    def test_add_a_note_shows_the_hotkey(self):
        row = menu_model.view(FINE, now=NOW, hotkey="⌃⌥N")["rows"][0]
        self.assertEqual((row["id"], row["detail"]), ("add_note", "⌃⌥N"))

    def test_check_access_says_how_many_are_off_and_where_it_goes(self):
        def row(s):
            return next(r for r in menu_model.view(s, now=NOW)["rows"] if r["id"] == "access")
        self.assertNotIn("detail", row(FINE))
        self.assertEqual(row(status(screen=False))["detail"], "1 off")
        self.assertEqual(row(status(screen=False, mic_off=True))["detail"], "2 off")
        self.assertEqual(menu_model.access_action(FINE), "ok")
        self.assertEqual(menu_model.access_action(status(screen=False)), "screen")
        self.assertEqual(menu_model.access_action(status(mic_off=True)), "mic")
        self.assertEqual(menu_model.access_action(status(screen=False, mic_off=True)), "screen")   # the one that is needed
        self.assertEqual(menu_model.access_action(status(screen=False, restart=True)), "restart")

    def test_when_macos_only_needs_a_restart_the_menu_says_so_first(self):
        v = menu_model.view(status(screen=False, restart=True), now=NOW)
        self.assertEqual((v["title"], v["line"], v["mark"]), ("Screen access is on", "Restart LMemM to finish.", "screen_off"))
        self.assertEqual(ids(v["rows"])[:2], ["restart", "-"])
        plain = menu_model.view(status(screen=False), now=NOW)
        self.assertEqual(plain["title"], "Screen access is off")
        self.assertNotIn("restart", ids(plain["rows"]))

    def test_the_questions_say_what_happens(self):
        title, text = menu_model.delete_words({"files": 8412, "bytes": 1_900_000_000})
        self.assertIn("8,412 files (1.9 GB)", text)
        self.assertIn("cannot be undone", text)
        self.assertIn("Your own files and apps are not touched", text)
        self.assertIn("1 file (12 KB)", menu_model.delete_words({"files": 1, "bytes": 12_000})[1])
        self.assertIn("notes stay", menu_model.setup_words()[1])
        self.assertEqual([menu_model.size_text(n) for n in (999, 1_000, 340_000_000, 1_900_000_000, 25_000_000_000)],
                         ["999 bytes", "1.0 KB", "340 MB", "1.9 GB", "25 GB"])

    def test_the_menu_offers_what_the_pill_offers(self):
        pill = [(o["kind"], o["title"], o["sub"]) for o in rules.pause_options(NOW)]
        menu = [(menu_model.pause_kind(c["id"]), c["title"], c["detail"])
                for c in next(r for r in menu_model.view(FINE, now=NOW)["rows"] if r["id"] == "pause")["children"]]
        self.assertEqual(menu, pill)

    def test_a_pause_you_chose_has_resume_and_an_automatic_one_has_nothing_to_do(self):
        mine = menu_model.view(status(paused="manual"), now=NOW)["rows"]
        self.assertEqual(ids(mine), ["add_note", "-", "resume", "-", "access", "setup", "-", "delete", "quit"])
        away = menu_model.view(status(paused="away"), now=NOW)["rows"]
        self.assertEqual(ids(away), ["add_note", "-", "access", "setup", "-", "delete", "quit"])

    def test_every_clickable_row_id_is_one_the_tracker_understands(self):
        known = {"resume", "quit", "add_note", "access", "setup", "delete", "restart"} | {"pause:" + k for k in rules.PAUSE_CHOICES}
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
        self.assertTrue({"pause_kind", "widget_pause", "widget_resume", "check_access", "confirm_leaving"} <= called)
        text = ast.unparse(fn)
        for row in ("resume", "quit", "add_note", "access", "restart", "setup", "delete"):
            self.assertIn(repr(row), text, row)
        self.assertIn("quit_requested", text)

    def test_deleting_and_reopening_setup_ask_first_and_cancel_does_nothing(self):
        import ast
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "src", "tracker.py")
        with open(path) as fh:
            tree = ast.parse(fh.read())
        fns = {n.name: n for c in tree.body if isinstance(c, ast.ClassDef) for n in c.body if isinstance(n, ast.FunctionDef)}
        pick = ast.unparse(fns["menu_pick"])
        self.assertLess(pick.index("confirm_leaving"), pick.index("after_exit"))       # asked before it is set
        self.assertIn("delete_words", ast.unparse(fns["confirm_leaving"]))
        self.assertIn("careful=True", ast.unparse(fns["confirm_leaving"]))
        hand = ast.unparse(fns["hand_over"])
        self.assertIn("delete_all", hand)
        self.assertIn("execv", hand)
        run = ast.unparse(fns["run"])
        self.assertLess(run.index("self.finish()"), run.index("self.hand_over()"))       # saved and stopped first


if __name__ == "__main__":
    unittest.main()
