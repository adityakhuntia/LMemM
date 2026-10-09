"""First-run setup (onboarding.py): the rules, the states, and a stress run. No Mac needed."""

import itertools
import json
import os
import random
import tempfile
import unittest
from datetime import date

import onboarding as ob

CHROME = {"id": "com.google.Chrome", "name": "Chrome"}
CODE = {"id": "com.microsoft.VSCode", "name": "VS Code"}


class FakeSystem:
    """Stands in for permissions.MacSystem: scripted facts, and a record of what was asked."""

    def __init__(self, **facts):
        self.state = {"screen": False, "screen_fresh": False, "ax": False, "mic": "notDetermined",
                      "speech": "notDetermined", **facts}
        self.calls, self.saved = [], []
        self.fail = set()
        self.name, self.lang, self.zone = "Aditya Khuntia", "en-IN", "Asia/Kolkata"

    def facts(self):
        if "facts" in self.fail:
            raise RuntimeError("macOS said no")
        return dict(self.state)

    def ask_voice(self):
        self._do("ask_voice")

    def open_settings(self, perm):
        self._do(f"settings:{perm}")

    def relaunch(self):
        self._do("relaunch")

    def _do(self, call):
        if call.split(":")[0] in self.fail:
            raise RuntimeError("could not")
        self.calls.append(call)

    def full_name(self):
        return self.name

    def language(self):
        return self.lang

    def time_zone(self):
        return self.zone

    def save_user(self, record):
        if "save_user" in self.fail:
            raise OSError("disk full")
        self.saved.append(record)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "data", "onboarding.json")

    def setup(self, system=None, **facts):
        self.system = system or FakeSystem(**facts)
        return ob.Setup(self.system, self.path, today=date(2026, 10, 9))

    def fresh(self, **facts):
        """A first run: no progress file on disk."""
        if os.path.exists(self.path):
            os.remove(self.path)
        return self.setup(**facts)

    def to(self, s, step):
        """Walk to a step with a valid name, the way a person would."""
        if not s.state["name"]:
            s.state["name"] = "Aditya"
        while s.step != step:
            self.assertTrue(s.next(), f"stuck before {step} at {s.step}")
        return s


class NameTests(unittest.TestCase):
    def test_sanitize(self):
        self.assertEqual(ob.sanitize_name("  Mary   Ann \n"), "Mary Ann")
        self.assertEqual(ob.sanitize_name("Ada\x00\x07Lovelace"), "AdaLovelace")
        self.assertEqual(ob.sanitize_name("a" * 100), "a" * ob.NAME_MAX)
        self.assertEqual(ob.sanitize_name("x" * 39 + " y"), "x" * 39)          # no trailing space after the cut
        self.assertEqual(ob.sanitize_name(None), "")
        self.assertEqual(ob.sanitize_name(42), "")
        self.assertEqual(ob.sanitize_name("Zoë 😀"), "Zoë 😀")

    def test_valid(self):
        for good in ("A", "Aditya", "李雷", "O'Brien", "7"):
            self.assertTrue(ob.valid_name(good), good)
        for bad in ("", "   ", "...", "-", "\n\t", None, 5):
            self.assertFalse(ob.valid_name(bad), repr(bad))


class PermissionStateTests(unittest.TestCase):
    def test_screen(self):
        self.assertEqual(ob.perm_state("screen", {"screen": True}), ob.GRANTED)
        self.assertEqual(ob.perm_state("screen", {"screen": True, "screen_fresh": False}), ob.GRANTED)
        self.assertEqual(ob.perm_state("screen", {"screen": False, "screen_fresh": True}), ob.RESTART)
        self.assertEqual(ob.perm_state("screen", {"screen": False, "screen_fresh": False}), ob.OFF)
        self.assertEqual(ob.perm_state("screen", {}), ob.OFF)
        self.assertEqual(ob.perm_state("screen", None), ob.OFF)

    def test_accessibility(self):
        self.assertEqual(ob.perm_state("ax", {"ax": True}), ob.GRANTED)
        self.assertEqual(ob.perm_state("ax", {"ax": False}), ob.OFF)
        self.assertEqual(ob.perm_state("ax", {}), ob.OFF)

    def test_voice_needs_both_and_names_a_refusal(self):
        words = ("authorized", "denied", "restricted", "notDetermined", None, "nonsense")
        for mic, speech in itertools.product(words, words):
            got = ob.perm_state("voice", {"mic": mic, "speech": speech})
            if mic == speech == "authorized":
                want = ob.GRANTED
            elif {mic, speech} & {"denied", "restricted"}:
                want = ob.DENIED
            else:
                want = ob.OFF
            self.assertEqual(got, want, (mic, speech))

    def test_unknown_permission_is_an_error(self):
        with self.assertRaises(ValueError):
            ob.perm_state("camera", {})

    def test_each_row_offers_one_action(self):
        self.assertEqual(ob.row_action("voice", ob.OFF), "allow")
        self.assertEqual(ob.row_action("voice", ob.DENIED), "settings")      # macOS will not ask again
        self.assertEqual(ob.row_action("ax", ob.OFF), "settings")
        self.assertEqual(ob.row_action("screen", ob.OFF), "settings")
        self.assertEqual(ob.row_action("screen", ob.RESTART), "restart")
        for perm in ob.PERMS:
            self.assertIsNone(ob.row_action(perm, ob.GRANTED))

    def test_screen_recording_is_last_so_one_restart_covers_all(self):     # S4
        self.assertEqual(ob.PERMS[-1], "screen")

    def test_row_lines(self):
        self.assertEqual(ob.row_line("voice", ob.DENIED), "Off. Turn it on in System Settings.")
        self.assertEqual(ob.row_line("screen", ob.RESTART), "Turned on. Restart to finish.")
        self.assertEqual(ob.row_line("screen", ob.OFF), "Knows which window you’re in.")
        self.assertEqual(ob.row_line("screen", ob.OFF, [CHROME, CODE]), "Only Chrome, VS Code. Off everywhere else.")
        self.assertEqual(ob.row_line("screen", ob.GRANTED, [CHROME, CODE, {"id": "x", "name": "Notes"}]),
                         "Only Chrome, VS Code +1. Off everywhere else.")
        self.assertIn("slower", ob.row_line("ax", ob.OFF))


class StateTests(unittest.TestCase):
    def test_normalize_repairs_anything(self):
        for junk in (None, 5, "x", [], {"step": 9}, {"step": "nope"}, {"name": 7, "roles": "Code"},
                     {"watch_apps": "Chrome"}, {"roles": ["Code", "Code", "Pirate", 3]}):
            state = ob.normalize(junk)
            self.assertEqual(state, ob.normalize(state))                  # already valid: unchanged
            self.assertIn(state["step"], ob.STEPS)

    def test_a_step_past_the_name_needs_a_name(self):
        for step in ("access", "try", "done"):
            self.assertEqual(ob.normalize({"step": step, "name": ""})["step"], "you")
            self.assertEqual(ob.normalize({"step": step, "name": "Ada"})["step"], step)
        self.assertEqual(ob.normalize({"step": "you", "name": ""})["step"], "you")
        self.assertEqual(ob.normalize({"step": "welcome", "name": ""})["step"], "welcome")

    def test_roles_keep_their_fixed_order_without_duplicates(self):
        got = ob.normalize({"roles": ["Research", "Code", "Research", "Nope"]})["roles"]
        self.assertEqual(got, ["Code", "Research"])

    def test_corrupt_file_starts_fresh(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "o.json")
            for text in ("", "{", "[1,2]", "null", '{"step":'):
                with open(path, "w") as fh:
                    fh.write(text)
                self.assertEqual(ob.load_state(path), ob.fresh_state())
        self.assertEqual(ob.load_state("/definitely/not/here.json"), ob.fresh_state())

    def test_needs_setup_until_completed(self):                              # S7
        self.assertTrue(ob.needs_setup(ob.fresh_state()))
        self.assertFalse(ob.needs_setup(ob.normalize({"completed": True})))
        self.assertTrue(ob.needs_setup(ob.normalize({"completed": "yes"})))


class FlowTests(Base):
    def test_starts_on_welcome_with_an_empty_name(self):
        s = self.setup()
        self.assertEqual(s.step, "welcome")
        self.assertEqual(s.state["name"], "")
        self.assertFalse(s.view()["back"])                                  # S1: nothing before the first screen

    def test_the_name_field_starts_empty_whatever_the_mac_account_is_called(self):
        system = FakeSystem()
        system.name = "Aditya Khuntia"
        s = self.setup(system)
        self.assertEqual(s.state["name"], "")
        s.next()
        v = s.view()
        self.assertEqual(v["name"]["value"], "")
        self.assertEqual(v["name"]["placeholder"], "First name")
        self.assertFalse(v["primary"]["enabled"])

    def test_a_name_already_typed_is_kept(self):
        ob.save_state(self.path, {**ob.fresh_state(), "name": "Ada"})
        self.assertEqual(self.setup().state["name"], "Ada")

    def test_every_screen_but_the_first_has_back(self):                      # S1
        s = self.setup()
        for step in ob.STEPS[1:]:
            self.to(s, step)
            self.assertTrue(s.view()["back"], step)
            self.assertTrue(s.back())
            self.assertTrue(s.next())
        self.assertFalse(self.fresh().back())

    def test_continue_on_you_waits_for_a_name_and_only_there(self):          # S1, S2
        s = self.setup()
        s.state["name"] = ""
        self.assertTrue(s.next())                                           # welcome → you
        self.assertFalse(s.next())
        self.assertFalse(s.view()["primary"]["enabled"])
        self.assertEqual(s.view()["name"]["hint"], "Just a first name is fine.")
        self.assertFalse(s.press_primary())
        s.set_name("...")
        self.assertFalse(s.next())
        s.set_name("  Ada  ")
        self.assertEqual(s.state["name"], "Ada")
        self.assertTrue(s.view()["primary"]["enabled"])
        self.assertTrue(s.next())

    def test_name_roles_and_apps_only_change_on_their_own_screen(self):
        s = self.setup()
        self.assertFalse(s.set_name("Bob"))
        self.assertFalse(s.toggle_role("Code"))
        self.assertFalse(s.set_apps([CHROME]))
        self.to(s, "you")
        self.assertTrue(s.set_name("Bob") and s.toggle_role("Code"))
        self.assertFalse(s.set_apps([CHROME]))
        self.to(s, "access")
        self.assertTrue(s.set_apps([CHROME]))
        self.assertFalse(s.set_name("Eve"))
        self.assertFalse(s.toggle_role("Design"))
        self.assertEqual((s.state["name"], s.state["roles"]), ("Bob", ["Code"]))

    def test_roles_toggle_and_stay_in_order(self):
        s = self.to(self.setup(), "you")
        for r in ("Research", "Code", "Research", "Nope"):
            s.toggle_role(r)
        self.assertEqual(s.state["roles"], ["Code"])
        s.toggle_role("Writing")
        self.assertEqual(s.state["roles"], ["Code", "Writing"])
        self.assertEqual([r["name"] for r in s.view()["roles"] if r["on"]], ["Code", "Writing"])

    def test_nothing_past_the_last_screen_and_nothing_before_the_first(self):
        s = self.to(self.setup(), "done")
        self.assertFalse(s.next())
        self.assertFalse(self.fresh().back())

    def test_every_press_is_saved_and_a_new_run_resumes(self):               # S6 / resume
        s = self.to(self.setup(), "access")
        s.state["name"] = "Ada"
        s.next()
        self.assertEqual(ob.load_state(self.path), s.state)
        again = self.setup()
        self.assertEqual((again.step, again.state["name"]), ("try", "Ada"))

    def test_nothing_is_written_to_memory_before_done(self):                 # S6
        s = self.to(self.setup(), "done")
        self.assertEqual(self.system.saved, [])
        self.assertTrue(s.finish())
        self.assertEqual(len(self.system.saved), 1)

    def test_finish_only_on_done(self):
        s = self.to(self.setup(), "try")
        self.assertFalse(s.finish())
        self.assertEqual(self.system.saved, [])

    def test_finish_writes_the_user_once_and_closes_setup(self):
        s = self.to(self.setup(), "done")
        self.assertTrue(s.finish())
        self.assertTrue(s.completed)
        self.assertFalse(s.finish())
        self.assertEqual(len(self.system.saved), 1)
        for press in (s.next, s.back, lambda: s.set_name("X"), lambda: s.toggle_role("Code")):
            self.assertFalse(press())
        self.assertFalse(ob.needs_setup(self.setup().state))

    def test_a_failed_save_is_calm_and_can_be_retried(self):
        s = self.to(self.setup(), "done")
        self.system.fail.add("save_user")
        self.assertTrue(s.finish())
        self.assertFalse(s.completed)
        self.assertIn("Try Done again", s.view()["error"])
        self.system.fail.clear()
        self.assertTrue(s.finish())
        self.assertTrue(s.completed)
        self.assertIsNone(s.view()["error"] if not s.completed else None)

    def test_progress_that_cannot_be_written_does_not_block_setup(self):
        os.makedirs(os.path.dirname(self.path))
        os.makedirs(self.path + ".tmp")                                     # writing the file will fail
        s = self.setup()
        self.assertTrue(s.next())
        self.assertIn("Couldn’t save your progress", s.view()["error"])
        self.assertEqual(s.step, "you")

    def test_rehearsal_counts_once_and_only_on_try(self):
        s = self.setup()
        self.assertFalse(s.rehearsed())
        self.to(s, "try")
        self.assertTrue(s.rehearsed())
        self.assertFalse(s.rehearsed())
        v = s.view()
        self.assertEqual(v["primary"]["label"], "Continue")
        self.assertIsNone(v["secondary"])
        self.assertEqual(v["notes"][0]["lead"], "That’s a note.")

    def test_try_can_always_be_skipped(self):
        v = self.to(self.setup(), "try").view()
        self.assertEqual(v["keys"], ["⌃", "⌥", "N"])
        self.assertEqual(v["primary"]["action"], "show_note")
        self.assertEqual(v["secondary"], {"label": "Skip for now", "action": "next"})


class AccessTests(Base):
    def row(self, s, key):
        return next(r for r in s.view()["rows"] if r["key"] == key)

    def test_rows_are_in_order_with_their_tags(self):
        s = self.to(self.setup(), "access")
        rows = s.view()["rows"]
        self.assertEqual([r["key"] for r in rows], ["voice", "ax", "screen"])
        self.assertEqual([r["tag"] for r in rows], [None, "Optional", "Needed"])
        self.assertEqual([r["button"] for r in rows], ["Allow", "Open System Settings", "Open System Settings"])

    def test_rows_follow_macos_live(self):                                   # S3
        s = self.to(self.setup(), "access")
        self.assertEqual(self.row(s, "ax")["state"], ob.OFF)
        self.system.state["ax"] = True
        self.assertTrue(s.refresh())
        self.assertEqual(self.row(s, "ax")["state"], ob.GRANTED)
        self.assertIsNone(self.row(s, "ax")["action"])
        self.system.state["ax"] = False                                      # switched back off in Settings
        s.refresh()
        self.assertEqual(self.row(s, "ax")["state"], ob.OFF)
        self.assertFalse(s.refresh())                                        # nothing changed: no redraw

    def test_voice_denied_goes_to_settings_not_back_to_a_prompt(self):
        s = self.to(self.setup(mic="denied", speech="authorized"), "access")
        row = self.row(s, "voice")
        self.assertEqual((row["state"], row["action"]), (ob.DENIED, "settings"))
        self.assertFalse(s.press("allow", "voice"))                          # only the offered action works
        self.assertTrue(s.press("settings", "voice"))
        self.assertEqual(self.system.calls, ["settings:voice"])

    def test_allow_voice_asks_macos_once_per_press(self):
        s = self.to(self.setup(), "access")
        self.assertTrue(s.press("allow", "voice"))
        self.assertEqual(self.system.calls, ["ask_voice"])
        self.assertFalse(s.press("settings", "voice"))                      # not what the row offers

    def test_granted_rows_do_nothing(self):
        s = self.to(self.setup(ax=True, screen=True, mic="authorized", speech="authorized"), "access")
        for perm in ob.PERMS:
            for action in ("allow", "settings", "restart"):
                self.assertFalse(s.press(action, perm), (perm, action))
        self.assertEqual(self.system.calls, [])

    def test_presses_only_work_on_the_access_screen(self):
        s = self.to(self.setup(), "you")
        self.assertFalse(s.press("settings", "screen"))
        self.assertEqual(self.system.calls, [])

    def test_unknown_permission_or_action_is_ignored(self):
        s = self.to(self.setup(), "access")
        for args in (("settings", "camera"), ("nonsense", "ax"), ("settings", None), (None, None)):
            self.assertFalse(s.press(*args), args)

    def test_screen_recording_turned_on_needs_a_restart(self):
        s = self.to(self.setup(screen=False, screen_fresh=True), "access")
        row = self.row(s, "screen")
        self.assertEqual((row["state"], row["action"], row["button"]), (ob.RESTART, "restart", "Restart LMemM"))
        self.assertEqual(row["line"], "Turned on. Restart to finish.")
        self.assertFalse(s.press("settings", "screen"))
        self.assertTrue(s.press("restart"))
        self.assertEqual(self.system.calls, ["relaunch"])

    def test_restart_resumes_on_the_same_screen_with_the_same_answers(self):
        s = self.to(self.setup(screen=False, screen_fresh=True), "access")
        s.state["name"] = "Ada"
        s.next()                                                             # on "try"
        s.back()
        s.set_apps([CHROME, CODE])
        s.press("restart")                                                   # the process would be replaced here
        after = self.setup(screen=True, screen_fresh=True)                   # the new run: macOS now allows it
        self.assertEqual((after.step, after.state["name"], after.state["watch_apps"]), ("access", "Ada", [CHROME, CODE]))
        self.assertEqual(self.row(after, "screen")["state"], ob.GRANTED)

    def test_a_restart_that_fails_says_so_and_changes_nothing(self):
        s = self.to(self.setup(screen=False, screen_fresh=True), "access")
        before = dict(s.state)
        self.system.fail.add("relaunch")
        self.assertTrue(s.press("restart"))
        self.assertIn("Couldn’t restart", s.view()["error"])
        self.assertEqual(s.state, before)
        self.assertTrue(s.next())                                            # and setup still goes on

    def test_a_failed_settings_open_is_calm(self):
        s = self.to(self.setup(), "access")
        self.system.fail.add("settings")
        self.assertTrue(s.press("settings", "ax"))
        self.assertIn("Couldn’t open System Settings", s.view()["error"])
        self.system.fail.clear()
        s.press("settings", "ax")
        self.assertIsNone(s.view()["error"])

    def test_facts_that_cannot_be_read_keep_the_last_ones(self):
        s = self.to(self.setup(ax=True), "access")
        self.system.fail.add("facts")
        self.assertFalse(s.refresh())
        self.assertEqual(self.row(s, "ax")["state"], ob.GRANTED)

    def test_the_button_never_changes_its_word_and_is_never_off(self):       # skipped permissions don't trap
        for facts in ({}, {"screen": True}, {"screen_fresh": True}, {"ax": True}):
            s = self.to(self.setup(**facts), "access")
            p = s.view()["primary"]
            self.assertEqual((p["label"], p["enabled"]), ("Continue", True))

    def test_the_button_is_solid_once_screen_is_on_or_apps_are_chosen(self):
        s = self.to(self.setup(), "access")
        self.assertTrue(s.view()["primary"]["quiet"])
        s.set_apps([CHROME])
        self.assertFalse(s.view()["primary"]["quiet"])                       # a choice was made: no "without it"
        s.set_apps([])
        self.assertTrue(s.view()["primary"]["quiet"])
        self.system.state["screen"] = True
        s.refresh()
        self.assertFalse(s.view()["primary"]["quiet"])
        self.system.state.update(screen=False, screen_fresh=True)
        s.refresh()
        self.assertFalse(s.view()["primary"]["quiet"])                       # restart pending still counts

    def test_the_trust_line_is_on_every_screen_that_asks_for_something(self):
        s = self.setup()
        self.assertIn("Nothing goes to the cloud", s.view()["trust"])
        self.to(s, "you")
        self.assertIn("Delete it any time", s.view()["trust"])
        self.to(s, "access")
        self.assertEqual(s.view()["trust"], ob.TRUST)
        self.assertIn("Never uploaded", ob.TRUST)

    def test_the_you_screen_says_what_is_saved(self):
        v = self.to(self.setup(), "you").view()
        self.assertEqual(len(v["saved"]), 4)
        self.assertIn("first name", v["saved"][0])


class DoneTests(Base):
    def test_done_with_everything_on(self):
        s = self.to(self.setup(ax=True, screen=True, mic="authorized", speech="authorized"), "done")
        v = s.view()
        self.assertEqual(v["title"], "You’re set, Aditya.")
        self.assertEqual(v["notes"], [])
        self.assertEqual((v["primary"]["label"], v["primary"]["action"]), ("Done", "finish"))
        self.assertIsNone(v["secondary"])

    def test_done_names_what_is_limited(self):
        s = self.to(self.setup(screen=True), "access")
        s.set_apps([CHROME, CODE])
        s.next(); s.next()
        notes = [n["text"] for n in s.view()["notes"]]
        self.assertTrue(any("watches only Chrome, VS Code" in n for n in notes))
        self.assertTrue(any("Accessibility is off" in n and "slower" in n for n in notes))

    def test_done_with_screen_off_still_finishes_and_says_what_the_pill_will_show(self):
        s = self.to(self.setup(), "done")
        v = s.view()
        self.assertEqual(v["primary"]["action"], "finish")
        self.assertTrue(any("red mark" in n["text"] for n in v["notes"]))
        self.assertTrue(s.press_primary())
        self.assertTrue(s.completed)

    def test_done_with_a_restart_pending_offers_restart_and_not_now(self):
        s = self.to(self.setup(screen=False, screen_fresh=True), "done")
        v = s.view()
        self.assertEqual((v["primary"]["label"], v["primary"]["action"]), ("Restart LMemM", "restart"))
        self.assertEqual(v["secondary"], {"label": "Not now", "action": "finish"})
        self.assertFalse(s.completed)
        self.assertTrue(s.finish())                                          # "Not now" is a way out
        self.assertTrue(s.completed)

    def test_a_blank_name_never_reaches_the_greeting_or_the_record(self):
        s = self.to(self.setup(), "done")
        s.state["name"] = ""
        self.assertEqual(s.view()["title"], "You’re set, there.")
        self.assertFalse(s.finish())


class RecordTests(unittest.TestCase):
    def test_record_has_only_what_the_screens_said(self):
        state = ob.normalize({"name": "Ada", "roles": ["Writing", "Code"], "watch_apps": [CHROME]})
        rec = ob.user_record(state, date(2026, 10, 9), "en-IN", "Asia/Kolkata")
        self.assertEqual(rec, {"name": "Ada", "works_on": ["code", "writing"], "watch_apps": [CHROME],
                               "language": "en-IN", "time_zone": "Asia/Kolkata",
                               "set_up": "2026-10-09", "onboarding": ob.VERSION})

    def test_optional_fields_are_left_out_when_empty(self):
        rec = ob.user_record(ob.normalize({"name": "Ada"}), date(2026, 10, 9), None, "  ")
        self.assertEqual(sorted(rec), ["name", "onboarding", "set_up"])

    def test_record_is_json(self):
        json.dumps(ob.user_record(ob.normalize({"name": "Zoë", "roles": ["Design"]}), date(2026, 10, 9), "fr", "UTC"))

    def test_language_and_zone_are_bounded(self):
        rec = ob.user_record(ob.normalize({"name": "Ada"}), date(2026, 10, 9), "x" * 80, 5)
        self.assertNotIn("language", rec)
        self.assertNotIn("time_zone", rec)


class SystemFailureTests(Base):
    def test_a_system_that_throws_everywhere_still_gives_a_working_setup(self):
        system = FakeSystem()
        system.fail = {"facts"}
        system.language = lambda: 1 / 0
        s = self.setup(system)
        s.state["name"] = "Ada"
        self.to(s, "done")
        self.assertTrue(s.finish())
        self.assertNotIn("language", system.saved[0])


class EveryRoadEndsTests(Base):
    """S1, exhaustively: whatever macOS says, however many apps are chosen, the main button alone
    (plus 'Not now') gets a person from the first screen to the end."""

    def test_no_combination_of_permissions_traps_anyone(self):
        screen = [(False, False), (False, True), (True, True)]
        words = ["notDetermined", "authorized", "denied", "restricted"]
        count = 0
        for (scr, fresh), ax, mic, speech, apps_ in itertools.product(screen, (False, True), words, words, ([], [CHROME])):
            with self.subTest(screen=scr, fresh=fresh, ax=ax, mic=mic, speech=speech, apps=bool(apps_)):
                if os.path.exists(self.path):
                    os.remove(self.path)
                s = self.setup(screen=scr, screen_fresh=fresh, ax=ax, mic=mic, speech=speech)
                s.state["watch_apps"] = list(apps_)
                for _ in range(12):
                    view = s.view()
                    self.assertIsNotNone(view["primary"])
                    if s.completed:
                        break
                    action = view["primary"]["action"]
                    if s.step == "you" and not view["primary"]["enabled"]:
                        self.assertTrue(s.set_name("Ada"))                 # a person has to type a name
                        continue
                    if action == "show_note":                              # the window's job; Skip is always there
                        self.assertEqual(view["secondary"]["action"], "next")
                        self.assertTrue(s.next())
                    elif action == "restart":                              # restart, and the new run is allowed
                        self.assertTrue(s.press_primary())
                        self.assertEqual(self.system.calls[-1], "relaunch")
                        self.system.state.update(screen=True, screen_fresh=True)
                        s = ob.Setup(self.system, self.path, today=date(2026, 10, 9))
                    else:
                        self.assertTrue(s.press_primary(), f"stuck on {s.step} with {action}")
                self.assertTrue(s.completed, s.step)
                self.assertEqual(len(self.system.saved), 1)
                count += 1
        self.assertEqual(count, 3 * 2 * 4 * 4 * 2)


class StressTests(Base):
    """Random presses, in any order, with random facts and restarts: the invariants never break."""

    NAMES = ["", "  ", "Ada", "Zoë 李", "\x00\x01", "x" * 200, "...", "A\nB", None, 5, "  a  b  "]
    ENTRIES = [[], [CHROME], [CODE, CHROME], "Chrome", [{"id": ""}], [None, 3], [CHROME, CHROME],
               [{"id": "a" * 50, "name": "n" * 500}], None, ["bare.id"]]

    def check(self, s):
        st = s.state
        self.assertEqual(st, ob.normalize(st), "state must always be valid")
        self.assertIn(st["step"], ob.STEPS)
        self.assertEqual(st["name"], ob.sanitize_name(st["name"]))
        if st["step"] != "welcome" and st["step"] != "you":
            self.assertTrue(ob.valid_name(st["name"]), f"past 'you' without a name: {st}")
        if st["completed"]:
            self.assertEqual(st["step"], "done")
            self.assertTrue(len(self.system.saved) >= 1)
        v = s.view()
        self.assertIn("title", v)
        self.assertIsNotNone(v["primary"])
        self.assertEqual(v["back"], st["step"] != "welcome")
        if st["step"] == "you":
            self.assertEqual(v["primary"]["enabled"], ob.valid_name(st["name"]))
        else:
            self.assertTrue(v["primary"]["enabled"])
        for row in v["rows"]:
            self.assertEqual(row["action"], ob.row_action(row["key"], row["state"]))
        self.assertEqual(ob.load_state(self.path), st, "what is on disk is what is in memory")
        json.dumps(v)

    def test_random_sequences(self):
        rng = random.Random(20261009)
        for run in range(300):
            if os.path.exists(self.path):
                os.remove(self.path)
            s = self.setup(FakeSystem())
            for _ in range(80):
                op = rng.choice(["next", "back", "name", "role", "apps", "press", "rehearsed", "finish",
                                 "primary", "facts", "reload", "fail", "heal"])
                if op == "next":
                    s.next()
                elif op == "back":
                    s.back()
                elif op == "name":
                    s.set_name(rng.choice(self.NAMES))
                elif op == "role":
                    s.toggle_role(rng.choice(list(ob.ROLES) + ["Pirate", None]))
                elif op == "apps":
                    s.set_apps(rng.choice(self.ENTRIES))
                elif op == "press":
                    s.press(rng.choice(["allow", "settings", "restart", "x", None]), rng.choice(list(ob.PERMS) + ["camera", None]))
                elif op == "rehearsed":
                    s.rehearsed()
                elif op == "finish":
                    s.finish()
                elif op == "primary":
                    s.press_primary()
                elif op == "facts":
                    self.system.state.update(
                        screen=rng.random() < .4, screen_fresh=rng.random() < .6, ax=rng.random() < .5,
                        mic=rng.choice(["authorized", "denied", "notDetermined", "restricted", None]),
                        speech=rng.choice(["authorized", "denied", "notDetermined", "restricted", None]))
                    s.refresh()
                elif op == "reload":                                        # quit and open again
                    s = ob.Setup(self.system, self.path, today=date(2026, 10, 9))
                elif op == "fail":
                    self.system.fail.add(rng.choice(["relaunch", "settings", "ask_voice", "save_user", "facts"]))
                else:
                    self.system.fail.clear()
                self.check(s)


if __name__ == "__main__":
    unittest.main()
