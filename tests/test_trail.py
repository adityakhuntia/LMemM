import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config
import trail_ax
import trail_engine
import trail_place
from trail_ax import Snapshot, collect
from trail_engine import Bursts, Engine, Gate, Scheduler, redact
from trail_place import PlaceTracker, place
from trail_store import TrailStore


class Node:
    """A fake accessibility node."""
    def __init__(self, role, children=(), **attrs):
        self._a = {"AXRole": role, **{"AX" + k: v for k, v in attrs.items()}}
        self._kids = list(children)

    def attrs(self):
        return self._a

    def children(self):
        return self._kids


def text(t, y=0, x=0):
    return Node("AXStaticText", Value=t, Position=(x, y))


def snap(**kw):
    return Snapshot(**kw)


WA = ("WhatsApp", "net.whatsapp.WhatsApp")
CHROME = ("Google Chrome", "com.google.Chrome")


class CollectTests(unittest.TestCase):
    def test_reads_title_text_headings_and_selected_row_in_reading_order(self):
        row = Node("AXRow", [text("Mum", y=100), text("see you at 6", y=110), text("10:02", y=120)], Selected=True)
        win = Node("AXWindow", [text("second", y=40), text("first", y=10),
                                Node("AXHeading", Title="Mum"), Node("AXList", [row])], Title="WhatsApp")
        s = collect(win)
        self.assertEqual(s.title, "WhatsApp")
        self.assertEqual(s.texts[:2], ["first", "second"])
        self.assertEqual(s.headings, ["Mum"])
        self.assertEqual(s.selected, [["Mum", "see you at 6", "10:02"]])

    def test_a_password_field_is_never_read_and_marks_focus_secure(self):
        pw = Node("AXTextField", Subrole="AXSecureTextField", Value="hunter2")
        win = Node("AXWindow", [pw, text("Sign in")])
        s = collect(win, focus=pw)
        self.assertTrue(s.focus_secure)
        self.assertNotIn("hunter2", " ".join(s.texts))

    def test_typed_text_is_not_read(self):
        box = Node("AXTextArea", Value="my secret draft", PlaceholderValue="Type a message to Mum")
        s = collect(Node("AXWindow", [box]), focus=box)
        self.assertEqual(s.focus_label, "Type a message to Mum")
        self.assertNotIn("my secret draft", " ".join(s.texts))

    def test_budgets_stop_a_huge_tree(self):
        win = Node("AXWindow", [Node("AXGroup", [text(f"t{i}") for i in range(80)]) for _ in range(30)])
        s = collect(win, max_nodes=100)
        self.assertTrue(s.truncated)
        self.assertLessEqual(s.nodes, 100)
        t = iter(range(0, 10_000, 30))
        s = collect(win, clock=lambda: next(t) / 1000, max_ms=45)
        self.assertTrue(s.truncated)

    def test_a_browsers_chrome_does_not_eat_the_budget_the_page_is_read_first(self):
        chrome = Node("AXToolbar", [text(f"bookmark {i}") for i in range(60)])
        tabs = Node("AXTabGroup", [Node("AXRadioButton", Title="tab", Value=1) for _ in range(40)])
        page = Node("AXWebArea", [Node("AXGroup", [text("Mum"), text("hello")])], URL="https://web.whatsapp.com/")
        s = collect(Node("AXWindow", [chrome, tabs, Node("AXGroup", [page])], Title="WhatsApp"), max_nodes=20)
        self.assertEqual(s.url, "https://web.whatsapp.com/")
        self.assertEqual(s.texts, ["Mum", "hello"])

    def test_an_apps_own_shell_page_is_skipped_for_the_real_page(self):
        shell = Node("AXWebArea", URL="file:///Applications/X.app/index.html")
        page = Node("AXWebArea", [text("hi")], Title="Trip plan", URL="https://claude.ai/chat/abc")
        s = collect(Node("AXWindow", [Node("AXGroup", [shell, page])], Title="Claude"))
        self.assertEqual((s.url, s.page_title, s.texts), ("https://claude.ai/chat/abc", "Trip plan", ["hi"]))

    def test_a_selected_cell_with_only_a_description_is_read(self):
        cell = Node("AXCell", Selected=True, Description="Mum 10:02 pm see you")
        s = collect(Node("AXWindow", [cell]))
        self.assertEqual(s.selected, [["Mum 10:02 pm see you"]])

    def test_a_broken_node_never_raises(self):
        class Bad:
            def attrs(self): raise RuntimeError("AX timeout")
            def children(self): return []
        self.assertTrue(collect(Bad()).truncated)

    def test_light_read_walks_nothing(self):
        win = Node("AXWindow", [text("x")], Title="T")
        s = collect(win, max_nodes=0)
        self.assertEqual((s.title, s.nodes, s.truncated), ("T", 0, False))

    def test_thin(self):
        self.assertTrue(Snapshot(texts=["a"]).thin())
        self.assertFalse(Snapshot(headings=["x"]).thin())


class RouteTests(unittest.TestCase):
    def test_two_chatgpt_conversations_have_two_keys_though_the_title_is_the_same(self):
        a = place(*CHROME, snap(title="ChatGPT", url="https://chatgpt.com/c/aaaaaaaa-1111-2222"))
        b = place(*CHROME, snap(title="ChatGPT", url="https://chatgpt.com/c/bbbbbbbb-3333-4444"))
        self.assertNotEqual(a["key"], b["key"])
        self.assertEqual((a["kind"], a["confidence"]), ("ai_chat", 1.0))

    def test_same_conversation_with_a_changed_title_keeps_its_key(self):
        a = place(*CHROME, snap(title="New chat", url="https://chatgpt.com/c/aaaaaaaa-1111"))
        b = place(*CHROME, snap(title="Trip plan - ChatGPT", url="https://chatgpt.com/c/aaaaaaaa-1111?model=x"))
        self.assertEqual(a["key"], b["key"])

    def test_new_conversation_without_an_id(self):
        p = place(*CHROME, snap(title="ChatGPT", url="https://chatgpt.com/"))
        self.assertEqual((p["kind"], p["key"]), ("ai_chat", "ChatGPT:ai_chat:new"))

    def test_slack_channels_by_url(self):
        a = place(*CHROME, snap(title="Slack", url="https://app.slack.com/client/T01ABC/C0GENERAL"))
        b = place(*CHROME, snap(title="Slack", url="https://app.slack.com/client/T01ABC/C0RANDOM"))
        self.assertNotEqual(a["key"], b["key"])
        self.assertEqual(a["kind"], "chat")

    def test_gmail_thread_and_inbox_differ(self):
        t = place(*CHROME, snap(title="Re: lunch", url="https://mail.google.com/mail/u/0/#inbox/FMfcgzQXKkLpPzAbCdEfGh"))
        i = place(*CHROME, snap(title="Inbox", url="https://mail.google.com/mail/u/0/#inbox"))
        self.assertEqual(t["kind"], "email")
        self.assertNotEqual(t["key"], i["key"])

    def test_google_sheet_tabs_differ(self):
        base = "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWx/edit"
        a = place(*CHROME, snap(title="Budget", url=base + "#gid=0"))
        b = place(*CHROME, snap(title="Budget", url=base + "#gid=77"))
        self.assertNotEqual(a["key"], b["key"])

    def test_an_ordinary_page_ignores_tracking_params_and_fragment(self):
        a = place(*CHROME, snap(title="Pricing - Google Chrome", url="https://example.com/pricing?utm_source=x#top"))
        b = place(*CHROME, snap(title="Pricing", url="https://example.com/pricing/"))
        self.assertEqual(a["key"], b["key"])
        self.assertEqual(a["name"], "Pricing")

    def test_youtube_videos_differ(self):
        a = place(*CHROME, snap(title="v1", url="https://www.youtube.com/watch?v=abc"))
        b = place(*CHROME, snap(title="v2", url="https://www.youtube.com/watch?v=def"))
        self.assertNotEqual(a["key"], b["key"])


class ChatTests(unittest.TestCase):
    def wa(self, label="", selected=None, title="WhatsApp", headings=()):
        return place(*WA, snap(title=title, focus_label=label, selected=selected or [], headings=list(headings)))

    def test_two_chats_in_one_window_are_two_places(self):
        a = self.wa("Type a message to Mum", [["Mum", "ok"]])
        b = self.wa("Type a message to Priya", [["Priya", "hi"]])
        self.assertNotEqual(a["key"], b["key"])
        self.assertEqual(a["name"], "Mum")
        self.assertGreaterEqual(a["confidence"], 0.8)

    def test_agreeing_signals_beat_one(self):
        one = self.wa("Type a message to Mum")
        two = self.wa("Type a message to Mum", [["Mum", "x"]], headings=["Mum"])
        self.assertGreater(two["confidence"], one["confidence"])
        self.assertEqual(one["key"], two["key"])

    def test_unread_badges_and_case_do_not_make_a_new_chat(self):
        a = self.wa(selected=[["Mum", "x"]])
        b = self.wa(selected=[["(3) MUM", "x"]])
        self.assertEqual(a["key"], b["key"])

    def test_disagreement_is_reported_with_low_confidence(self):
        p = self.wa("Type a message to Mum", [["Priya", "x"]])
        self.assertTrue(p["conflict"])
        self.assertLess(p["confidence"], 0.5)

    def test_unreadable_chat_has_an_unknown_key_not_a_wrong_one(self):
        p = self.wa()
        self.assertTrue(p["key"].endswith(":?"))
        self.assertEqual(p["kind"], "chat")

    def test_whatsapp_web_names_the_chat_from_the_page_not_the_tab_title(self):
        s = snap(title="WhatsApp", url="https://web.whatsapp.com/", focus_label="Type a message", selected=[["Priya", "k"]])
        p = place(*CHROME, s)
        self.assertEqual((p["kind"], p["name"], p["service"]), ("chat", "Priya", "WhatsApp"))
        self.assertEqual(p["key"], "WhatsApp:chat:priya")

    def test_a_sidebar_cell_that_is_one_description_gives_the_name_before_the_time(self):
        s = snap(title="WhatsApp", url="https://web.whatsapp.com/", focus_label="Type a message to group Team 10",
                 selected=[["Team 10 11:27 pm Hi I am testing"]])
        p = place(*CHROME, s)
        self.assertEqual(p["name"], "Team 10")
        self.assertGreaterEqual(p["confidence"], 0.9)

    def test_group_word_in_the_box_label_is_not_part_of_the_name(self):
        p = place(*CHROME, snap(title="WhatsApp", url="https://web.whatsapp.com/", focus_label="Type a message to group Team 10"))
        self.assertEqual(p["name"], "Team 10")

    def test_messages_app_uses_selected_conversation(self):
        p = place("Messages", "com.apple.MobileSMS", snap(title="Messages", selected=[["Dad", "call me"]]))
        self.assertEqual(p["name"], "Dad")

    def test_unknown_app_with_a_message_box_is_a_chat(self):
        p = place("Foo", "com.foo", snap(title="Foo", focus_label="Message #design", selected=[["design", ""]]))
        self.assertEqual(p["kind"], "chat")
        self.assertEqual(p["name"], "design")

    def test_ai_desktop_app_conversations_by_title(self):
        a = place("Claude", "com.anthropic.claudefordesktop", snap(title="Trip plan"))
        b = place("Claude", "com.anthropic.claudefordesktop", snap(title="Tax questions"))
        self.assertNotEqual(a["key"], b["key"])

    def test_claude_desktop_conversations_by_the_page_it_wraps(self):
        app = ("Claude", "com.anthropic.claudefordesktop")
        a = place(*app, snap(title="Claude", page_title="memModel - Claude Code",
                             url="https://claude.ai/epitaxy/project/chan_1?thread=cmsg_a"))
        b = place(*app, snap(title="Claude", page_title="Other thread - Claude Code",
                             url="https://claude.ai/epitaxy/project/chan_1?thread=cmsg_b"))
        self.assertNotEqual(a["key"], b["key"])
        self.assertEqual((a["kind"], a["name"], a["confidence"]), ("ai_chat", "memModel - Claude Code", 0.9))

    def test_vscode_file_and_folder(self):
        p = place("Code", "com.microsoft.VSCode", snap(title="tracker.py — LMemM — Visual Studio Code"))
        self.assertEqual((p["kind"], p["name"], p["container"]), ("code", "tracker.py", "LMemM"))


class StandardPipelineNameTests(unittest.TestCase):
    def test_an_accessibility_name_replaces_the_ocr_header(self):
        import understand
        res = {"objects": [{"text": "Divya•n$h Stth", "kind": "heading", "box": [900, 120, 200, 20]}],
               "image_size": {"w": 1600, "h": 900}}
        meta = {"app": "Brave Browser", "site": "web.whatsapp.com", "window": "WhatsApp", "trail_chat": "Divyaansh Seth"}
        st = understand.describe(res, meta)
        self.assertEqual((st["app"], st["target"]), ("WhatsApp", "Divyaansh Seth"))
        self.assertEqual(understand.ref(st), understand.ref(understand.chat_state("WhatsApp", "Divyaansh Seth")))

    def test_without_it_the_ocr_header_is_still_used(self):
        import understand
        res = {"objects": [{"text": "Mum", "kind": "heading", "box": [900, 20, 200, 20]}], "image_size": {"w": 1600, "h": 900}}
        st = understand.describe(res, {"app": "WhatsApp", "window": "WhatsApp"})
        self.assertEqual(st["target"], "Mum")

    def test_private_tabs_are_skipped(self):
        self.assertTrue(config.SKIP_TITLES.search("New Private Tab - Brave"))
        self.assertTrue(config.SKIP_TITLES.search("Reddit (Private)"))
        self.assertFalse(config.SKIP_TITLES.search("Private equity fund model - Google Sheets"))


class WarmTests(unittest.TestCase):
    def test_warm_touches_every_name_once_and_ignores_missing_ones(self):
        touched = []

        class Mod:
            def __getattr__(self, name):
                touched.append(name)
                if name == "missing":
                    raise AttributeError(name)
                return 1
        trail_ax.warm(Mod(), ("a", "missing", "b"))
        self.assertEqual(touched, ["a", "missing", "b"])


class SettleTests(unittest.TestCase):
    def P(self, key, conf=0.5, app="A", kind="chat"):
        return {"key": key, "app": app, "kind": kind, "confidence": conf, "name": key, "signals": [], "conflict": False, "url": ""}

    def test_first_place_is_accepted(self):
        t = PlaceTracker(150)
        self.assertEqual(t.update(self.P("a"), 0)["key"], "a")

    def test_a_shaky_switch_needs_to_repeat_or_wait(self):
        t = PlaceTracker(150)
        t.update(self.P("a", 0.9), 0)
        self.assertIsNone(t.update(self.P("b"), 100))
        self.assertEqual(t.pending_ms(100), 150)
        self.assertIsNone(t.update(self.P("b"), 200))
        self.assertEqual(t.update(self.P("b"), 260)["from_key"], "a")

    def test_a_flicker_that_returns_never_fires(self):
        t = PlaceTracker(150)
        t.update(self.P("a", 0.9), 0)
        t.update(self.P("b"), 100)
        self.assertIsNone(t.update(self.P("a", 0.9), 120))
        self.assertIsNone(t.cand)

    def test_a_certain_switch_and_an_app_switch_are_immediate(self):
        t = PlaceTracker(150)
        t.update(self.P("a", 0.9), 0)
        self.assertIsNotNone(t.update(self.P("b", 1.0), 10))
        self.assertIsNotNone(t.update(self.P("c", 0.2, app="B"), 20))

    def test_an_unreadable_chat_does_not_replace_a_known_one(self):
        t = PlaceTracker(150)
        t.update(self.P("a", 0.9), 0)
        self.assertIsNone(t.update(self.P("WhatsApp:chat:?"), 50))
        self.assertEqual(t.current["key"], "a")

    def test_dwell_is_reported(self):
        t = PlaceTracker(150)
        t.update(self.P("a", 0.9), 1000)
        self.assertEqual(t.update(self.P("b", 1.0), 6000)["dwell_ms"], 5000)


class SchedulerTests(unittest.TestCase):
    def test_bursts_of_changes_become_one_read(self):
        s = Scheduler(poll=100)
        for t in (1.00, 1.02, 1.04):
            s.poke("title", t)
        self.assertEqual(s.due(1.05), set())
        self.assertEqual(s.due(1.11), {"place"})
        self.assertEqual(s.due(1.12), set())

    def test_a_constant_stream_is_still_read_within_max_wait(self):
        s = Scheduler(poll=100)
        for i in range(30):
            s.poke("title", 1 + i * 0.02)
        self.assertEqual(s.due(1.26), {"place"})

    def test_app_switch_is_read_at_once(self):
        s = Scheduler(poll=100)
        s.poke("app", 5.0)
        self.assertEqual(s.due(5.0), {"place"})

    def test_text_is_rate_limited_per_interval(self):
        s = Scheduler(text_every=2.0, poll=100)
        s.poke("layout", 10.0)
        self.assertIn("text", s.due(10.0))
        s.poke("layout", 10.5)
        self.assertNotIn("text", s.due(11.0))
        self.assertIn("text", s.due(12.0))

    def test_wait_never_exceeds_the_poll_and_is_zero_when_due(self):
        s = Scheduler(poll=1.0)
        s.due(0)
        self.assertAlmostEqual(s.wait(0.2), 0.8)
        s.poke("app", 0.3)
        self.assertEqual(s.wait(0.3), 0)

    def test_idle_slows_polling_and_stops_text(self):
        s = Scheduler(poll=1.0, idle_poll=5.0)
        s.set_idle(True)
        s.poke("layout", 0)
        s.due(0)
        self.assertEqual(s.due(2.0), set())
        self.assertEqual(s.due(5.0), {"place"})


class GateTests(unittest.TestCase):
    def test_password_managers_and_lock_screen_are_skipped(self):
        g = Gate()
        self.assertEqual(g.app({"app": "1Password", "bundle_id": "com.1password.1password"}), "excluded_app")
        self.assertEqual(g.app({"app": "loginwindow", "bundle_id": "com.apple.loginwindow"}), "locked")
        self.assertEqual(g.app(None), "unidentified_app")
        self.assertIsNone(g.app({"app": "Notes", "bundle_id": "com.apple.Notes"}))

    def test_only_these_apps_fails_closed(self):
        g = Gate(watch_apps=[{"id": "com.apple.Notes", "name": "Notes"}])
        self.assertIsNone(g.app({"app": "Notes", "bundle_id": "com.apple.Notes"}))
        self.assertEqual(g.app({"app": "Mail", "bundle_id": "com.apple.mail"}), "not_in_watch_list")

    def test_private_windows_and_sensitive_sites(self):
        g = Gate()
        self.assertIsNotNone(g.page("", "Reddit - (Incognito)"))
        self.assertIsNotNone(g.page("", "Private Browsing"))
        self.assertIsNotNone(g.page("https://netbanking.hdfc.com/x", "x"))
        self.assertEqual(g.page("", "x", secure_focus=True), "secure_field")
        self.assertIsNone(g.page("https://example.com", "x"))


class FakeFront:
    def __init__(self, **kw):
        self.f = {"app": "WhatsApp", "bundle_id": "net.whatsapp.WhatsApp", "pid": 1}
        self.f.update(kw)

    def __call__(self):
        return self.f


class FakeReader:
    def __init__(self):
        self.light = snap(title="WhatsApp", focus_label="Type a message to Mum")
        self.full = snap(title="WhatsApp", focus_label="Type a message to Mum", selected=[["Mum", "x"]], texts=["hello"])
        self.calls = []

    def read(self, front, full):
        self.calls.append(full)
        return self.full if full else self.light


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = TrailStore(self.tmp.name, "t")
        self.front, self.reader = FakeFront(), FakeReader()
        self.e = Engine(self.store, self.front, self.reader)

    def kinds(self):
        return [(e["kind"], e.get("place", {}).get("name") if isinstance(e.get("place"), dict) else e.get("place"))
                for e in self.store.read()]

    def test_switching_chats_logs_each_chat_with_its_own_name(self):
        self.e.step({"place"}, 0)
        self.reader.light = snap(title="WhatsApp", focus_label="Type a message to Priya")
        self.reader.full = snap(title="WhatsApp", focus_label="Type a message to Priya", selected=[["Priya", "k"]])
        self.e.step({"place"}, 5)
        names = [e["place"]["name"] for e in self.store.read(kinds={"focus"})]
        self.assertEqual(names, ["Mum", "Priya"])
        self.assertEqual(self.store.read(kinds={"focus"})[1]["dwell_ms"], 5000)

    def test_nothing_changed_costs_one_light_read(self):
        self.e.step({"place"}, 0)
        self.reader.calls.clear()
        self.e.step({"place"}, 1)
        self.assertEqual(self.reader.calls, [False])

    def test_an_unsure_chat_escalates_to_a_full_read_a_sure_url_does_not(self):
        self.e.step({"place"}, 0)
        self.assertIn(True, self.reader.calls)
        self.front.f = {"app": "Google Chrome", "bundle_id": "com.google.Chrome", "pid": 2}
        self.reader.light = snap(title="ChatGPT", url="https://chatgpt.com/c/aaaaaaaa-1111-2222")
        self.reader.calls.clear()
        self.e.step({"place"}, 1)
        self.assertEqual(self.reader.calls, [False])

    def test_text_logs_only_what_is_new_and_what_left(self):
        self.reader.full.texts = ["hello", "how are you"]
        self.e.step({"place", "text"}, 0)
        self.reader.full.texts = ["how are you", "fine thanks"]
        self.e.step({"place", "text"}, 3)
        texts = self.store.read(kinds={"text"})
        self.assertEqual(texts[0]["added"], ["hello", "how are you"])
        self.assertEqual((texts[1]["added"], texts[1]["removed"]), (["fine thanks"], 1))

    def test_secrets_are_not_logged(self):
        self.assertEqual(redact(["ok", "4111111111111111", "key sk-abcdefghijklmnopqrstu", "password: abc"]), ["ok"])

    def test_an_excluded_app_is_never_read_and_never_named(self):
        self.front.f = {"app": "1Password", "bundle_id": "com.1password.1password", "pid": 9}
        self.e.step({"place", "text"}, 0)
        self.assertEqual(self.reader.calls, [])
        ev = self.store.read()
        self.assertEqual([(e["kind"], e.get("reason")) for e in ev], [("gap", "excluded_app")])
        self.assertNotIn("1Password", str(ev))

    def test_a_gap_is_logged_once_not_every_poll(self):
        self.front.f = {"app": "1Password", "bundle_id": "com.1password.1password", "pid": 9}
        for i in range(5):
            self.e.step({"place"}, i)
        self.assertEqual(len(self.store.read(kinds={"gap"})), 1)

    def test_secure_focus_logs_nothing_from_the_page(self):
        self.reader.light = snap(title="Sign in", focus_secure=True)
        self.e.step({"place", "text"}, 0)
        self.assertEqual([e["kind"] for e in self.store.read()], ["app_switch", "gap"])

    def test_pause_stops_everything(self):
        e = Engine(self.store, self.front, self.reader, paused=lambda: True)
        e.step({"place"}, 0)
        self.assertEqual(self.reader.calls, [])
        self.assertEqual(self.store.read()[0]["reason"], "paused")

    def test_typing_is_counted_and_never_recorded(self):
        self.e.step({"place"}, 0)
        for i in range(12):
            self.e.on_input("key", 1 + i * 0.1, field="Type a message to Mum")
        self.e.on_input("click", 5.0, target="Send")
        self.e.flush_bursts(5.0)
        ev = {x["kind"]: x for x in self.store.read(kinds={"typing", "click"})}
        self.assertEqual((ev["typing"]["n"], ev["typing"]["ms"]), (12, 1100))
        self.assertEqual(ev["click"]["target"], "Send")
        self.assertNotIn("key", ev["typing"])

    def test_input_without_a_known_place_is_dropped(self):
        self.e.on_input("key", 1)
        self.assertEqual(self.store.read(), [])

    def test_ocr_fallback_only_for_thin_screens_and_rate_limited(self):
        calls = []
        def vision(front, s):
            calls.append(1)
            return snap(texts=["Invoice 4412", "Total 120"], headings=["Invoice 4412"])
        e = Engine(self.store, FakeFront(app="Canvas", bundle_id="com.x.canvas"), FakeReader(), vision=vision)
        e.reader.full = snap(title="Canvas")
        e.reader.light = snap(title="Canvas")
        e.step({"place", "text"}, 0)
        e.step({"place", "text"}, 5)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.store.read(kinds={"text"})[0]["source"], "ocr")

    def test_no_screen_access_is_a_gap_not_a_crash(self):
        e = Engine(self.store, FakeFront(app="Canvas", bundle_id="com.x.canvas"), FakeReader(), vision=lambda f, s: None)
        e.reader.full = snap(title="Canvas")
        e.step({"place", "text"}, 0)
        self.assertIn("no_screen_access", [x.get("reason") for x in self.store.read(kinds={"gap"})])

    def test_ocr_off_by_config(self):
        old, config.TRAIL_VISION = config.TRAIL_VISION, False
        self.addCleanup(setattr, config, "TRAIL_VISION", old)
        calls = []
        e = Engine(self.store, FakeFront(app="Canvas", bundle_id="com.x.canvas"), FakeReader(), vision=lambda f, s: calls.append(1))
        e.reader.full = snap(title="Canvas")
        e.step({"place", "text"}, 0)
        self.assertEqual(calls, [])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
        self.s = TrailStore(self.tmp.name, "t", clock=lambda: self.now)

    def test_events_older_than_48_hours_are_not_returned_and_are_swept(self):
        self.s.add("x")
        self.now += timedelta(hours=47)
        self.assertEqual(len(self.s.read()), 1)
        self.now += timedelta(hours=2)
        self.assertEqual(self.s.read(), [])
        self.assertEqual(self.s.sweep(), 1)
        self.assertEqual(self.s.files(), [])

    def test_the_boundary_day_is_trimmed_not_dropped(self):
        self.s.add("old")
        self.now += timedelta(hours=40)
        self.s.add("mid")
        self.now += timedelta(hours=10)             # old is 50 h old, mid 10 h
        self.s.add("new")
        self.s.sweep()
        self.assertEqual([e["kind"] for e in self.s.read()], ["mid", "new"])

    def test_forget_last_minutes_one_app_and_everything(self):
        self.s.add("a", app="Mail")
        self.now += timedelta(minutes=30)
        self.s.add("b", app="Notes")
        self.s.add("c", app="Mail")
        self.assertEqual(self.s.forget(minutes=10), 2)
        self.assertEqual([e["kind"] for e in self.s.read()], ["a"])
        self.assertEqual(self.s.forget(app="Mail"), 1)
        self.s.add("d")
        self.assertEqual(self.s.forget(everything=True), 1)
        self.assertEqual(self.s.files(), [])

    def test_files_are_private_and_a_torn_line_is_skipped(self):
        self.s.add("x")
        self.s.flush()
        path = Path(self.tmp.name) / self.s.files()[0]
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(Path(self.tmp.name).stat().st_mode & 0o777 & 0o077, 0)
        with open(path, "a") as fh:
            fh.write('{"t": "2026-10')
        self.assertEqual(len(self.s.read()), 1)

    def test_size_cap_drops_the_oldest_day(self):
        s = TrailStore(self.tmp.name, "t", clock=lambda: self.now, max_mb=0.0005)
        s.add("a", pad="x" * 400)
        self.now += timedelta(days=1)
        s.add("b", pad="x" * 400)
        s.sweep()
        self.assertEqual([e["kind"] for e in s.read()], ["b"])

    def test_writes_are_buffered(self):
        for _ in range(3):
            self.s.add("x")
        self.assertEqual(self.s.files(), [])         # not on disk yet
        self.assertEqual(len(self.s.read()), 3)      # reading flushes

    def test_bad_retention_is_refused(self):
        with self.assertRaises(ValueError):
            TrailStore(self.tmp.name, retention_hours=0)


class BurstTests(unittest.TestCase):
    def test_a_pause_closes_a_burst_and_a_place_change_splits_it(self):
        b = Bursts()
        self.assertIsNone(b.feed("typing", 0, "a"))
        self.assertIsNone(b.feed("typing", 0.5, "a"))
        done = b.feed("typing", 5, "a")
        self.assertEqual((done["n"], done["ms"]), (2, 500))
        done = b.feed("typing", 5.1, "b")
        self.assertEqual(done["place"], "a")


if __name__ == "__main__":
    unittest.main()
