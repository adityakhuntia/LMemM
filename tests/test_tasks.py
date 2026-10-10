"""tasks.py: a session read as a story - the payload, the checked reply, the stored result. No macOS, no Claude."""

import json
import unittest

import config
import labels
import tasks
from test_labels import TmpPaths, excerpt, thing


def doc():
    rows = [("16:00:00", "16:20:00", "chatgpt", 1200), ("16:20:00", "16:30:00", "script", 600),
            ("16:30:00", "16:33:00", "sheet", 180), ("16:33:00", "16:50:00", "chatgpt", 1020),
            ("16:50:00", "16:50:05", "social", 5), ("16:51:00", "17:05:00", "script", 840)]
    return {"session": "20261010-160000", "timeline": [
        {"from": a, "to": b, "seconds": s, "item": i, "activity": {"typing": s // 2, "reading": s // 2}} for a, b, i, s in rows]}


def world():
    return {
        "chatgpt": thing("chatgpt", app="ChatGPT", title="Create Follow Up System", note_texts=["ask how triggers run"],
                         excerpts=[excerpt("The automation should check sent emails and reply after seven days of silence")]),
        "script": thing("script", app="script.google.com", title="Auto Send - Project Triggers - Apps Script",
                        excerpts=[excerpt("Triggers run the sendDrafts function every morning at eight o'clock")]),
        "sheet": thing("sheet", app="Google Docs", title="Outreach Tracker - Google Sheets"),
        "social": thing("social", app="Brave Browser", title="Instagram"),
    }


class FakeAsk:
    name = "fake"

    def __init__(self, reply):
        self.reply, self.calls = reply, []
        self.last_exchange = {"at": "t", "model": "m", "system_prompt": "s", "prompt": "p", "reply": reply, "usage": {}}

    def ask(self, payload, instruction=None, model=None, effort="low"):
        self.calls.append((payload, instruction, model, effort))
        return self.reply, {"input_tokens": 5, "cache_creation_input_tokens": 3000, "output_tokens": 200}


REPLY = json.dumps({"tasks": [
    {"title": "Build a follow-up email automation", "goal": "Reply after seven days of silence, mail to a@b.com", "stage": "Building",
     "things": [1, 2, 3, 99], "open": "Check the trigger", "project_guess": "Auto Send"},
    {"title": "Nothing real", "goal": "x", "stage": "weird", "things": [1], "open": None}], "other": ["THING 4", 2, 7]})


class TaskTests(TmpPaths):
    def test_the_payload_is_a_story_in_first_seen_order_with_the_visit_order(self):
        payload, ids = tasks.payload_for(doc(), world())
        self.assertEqual(ids[:3], ["chatgpt", "script", "sheet"])
        self.assertIn("Order of visits (THING numbers): 1 > 2 > 3 > 1 > 2", payload)
        self.assertIn("title: Create Follow Up System", payload)
        self.assertIn("16:00 to 17:05", payload)
        self.assertIn('open note: "ask how triggers run"', payload)
        self.assertNotIn("Instagram", payload)             # 5 s: a glance, left out

    def test_nothing_to_ask_with_fewer_than_two_things(self):
        d = {"session": "s", "timeline": doc()["timeline"][:1]}
        self.assertEqual(tasks.payload_for(d, world()), (None, []))

    def test_minutes_limits_the_stretch(self):
        _p, ids = tasks.payload_for(doc(), world(), minutes=20)
        self.assertNotIn("chatgpt", ids[:1])               # the first 20 minutes are before the window

    def test_the_reply_is_checked_and_mapped_to_item_ids(self):
        provider = FakeAsk(REPLY)
        result = tasks.run(doc(), world(), provider, labels.Governor(cap=50000))
        one = result["tasks"][0]
        self.assertEqual(one["items"], ["chatgpt", "script", "sheet"])        # 99 dropped
        self.assertEqual(one["stage"], "building")
        self.assertNotIn("a@b.com", one["goal"])
        self.assertEqual(len(result["tasks"]), 1)                              # the second task only reused thing 1
        self.assertEqual(result["other"], [])                                  # 4 is not in the story; 2 already used
        self.assertEqual(provider.calls[0][2:], (config.TASK_MODEL, "medium"))
        self.assertIn("A TASK is", provider.calls[0][1])
        self.assertEqual(tasks.load_tasks()["20261010-160000"]["tasks"][0]["title"], "Build a follow-up email automation")
        self.assertEqual(result["tasks"][0]["seconds"], 1200 + 600 + 180 + 1020 + 840)

    def test_dry_run_sends_nothing_and_the_cap_is_respected(self):
        provider = FakeAsk(REPLY)
        out = tasks.run(doc(), world(), provider, labels.Governor(cap=50000), dry_run=True)
        self.assertIsNone(out["stopped"])
        self.assertEqual(provider.calls, [])
        out = tasks.run(doc(), world(), provider, labels.Governor(cap=100))
        self.assertIn("limit", out["stopped"])
        self.assertEqual(provider.calls, [])

    def test_garbage_replies_give_no_tasks(self):
        self.assertEqual(tasks.parse("not json", 3), {"tasks": [], "other": []})
        self.assertEqual(tasks.parse('{"tasks": "x"}', 3), {"tasks": [], "other": []})

    def test_mail_and_messages_are_read_for_now_unless_switched_off(self):
        w = world()
        w["chatgpt"]["app"] = "WhatsApp"
        _p, ids = tasks.payload_for(doc(), w, events=[])
        self.assertIn("chatgpt", ids)
        old = config.TASK_OFF_APPS
        config.TASK_OFF_APPS = {"WhatsApp"}
        try:
            _p, ids = tasks.payload_for(doc(), w, events=[])
        finally:
            config.TASK_OFF_APPS = old
        self.assertNotIn("chatgpt", ids)

    def test_lmemms_own_terminal_text_stays_out(self):
        w = world()
        w["script"]["content"]["excerpts"] = [excerpt(
            "tasks: the garbled-text word-list filter was added to lmemm.py today, tick p95 is down")]
        payload, _ = tasks.payload_for(doc(), w, events=[])
        self.assertNotIn("garbled", payload)
        w["sheet"].update(app="Terminal", title="python3 lmemm.py tasks")
        _p, ids = tasks.payload_for(doc(), w, events=[])
        self.assertNotIn("sheet", ids)

    def test_addresses_in_screen_text_are_kept_but_secrets_are_not(self):
        w = world()
        w["chatgpt"]["content"]["excerpts"] = [excerpt(
            "Please send the proposal to maria.lopez@example.com before Friday evening"),
            excerpt("the api key sk-abcdefghijklmnopqrstuvwxyz123456 should go in the vault today")]
        payload, _ = tasks.payload_for(doc(), w, events=[])
        self.assertIn("maria.lopez@example.com", payload)
        self.assertNotIn("sk-abcdef", payload)


def ev(kind, t, **kw):
    return {"t": t, "kind": kind, **kw}


class WritingTests(TmpPaths):
    def at(self, hms):
        """A UTC timestamp for that local clock time on the session's day."""
        from datetime import datetime
        return datetime.strptime("20261010 " + hms, "%Y%m%d %H:%M:%S").astimezone().astimezone(
            __import__("datetime").timezone.utc).isoformat(timespec="milliseconds")

    def events(self):
        return [ev("write", self.at("16:05:00"), added=["Hi team, the reminder should go out after seven days."], app="ChatGPT"),
                ev("write", self.at("16:06:00"), added=["Hi team, the reminder should go out after seven days.",
                                                         "password: hunter2 is the login"], app="ChatGPT"),
                ev("typing", self.at("16:07:00"), n=240), ev("typing", self.at("16:08:00"), n=60),
                ev("write", self.at("16:25:00"), added=["function sendDrafts() sets the trigger to eight o'clock."], app="Chrome"),
                ev("write", self.at("12:00:00"), added=["written outside the session"], app="Notes")]

    def test_writing_lands_on_the_thing_open_at_that_moment_and_is_deduplicated(self):
        proof = tasks.evidence(doc(), world(), self.events())
        self.assertEqual(proof["chatgpt"]["wrote"], ["Hi team, the reminder should go out after seven days."])
        self.assertEqual(proof["chatgpt"]["keys"], 300)
        self.assertEqual(proof["script"]["wrote"], ["function sendDrafts() sets the trigger to eight o'clock."])
        self.assertNotIn("outside the session", json.dumps(proof))
        self.assertNotIn("hunter2", json.dumps(proof))

    def test_a_sentence_typed_over_several_reads_is_kept_once_in_its_final_form(self):
        pieces = ["No", "No so this", "No so this is before we", "No so this is before we made the followup edit.",
                  "Th", "The execution from Oct 9"]
        self.assertEqual(tasks.drop_drafts(pieces),
                         ["No so this is before we made the followup edit.", "The execution from Oct 9"])

    def test_the_payload_says_what_was_written_and_how_much_typing(self):
        payload, _ = tasks.payload_for(doc(), world(), events=self.events())
        self.assertIn("wrote:", payload)
        self.assertIn("the reminder should go out after seven days", payload)
        self.assertIn("~300 keystrokes", payload)

    def test_the_payload_shrinks_to_fit_the_ceiling(self):
        big = [ev("write", self.at("16:05:00"), added=[f"Sentence number {n} about the follow up system and its triggers."
                                                       for n in range(60)], app="ChatGPT")]
        full, _ = tasks.payload_for(doc(), world(), events=big, ceiling=10 ** 6)
        small, _ = tasks.payload_for(doc(), world(), events=big, ceiling=300)
        self.assertLess(len(small), len(full))
        self.assertIn("THING 1", small)          # the story is never dropped, only the evidence

    def test_writing_is_capped_per_thing(self):
        row = {"wrote": [f"Line {n} " + "x" * 100 for n in range(30)]}
        got = tasks.wrote_lines(row, tasks.WROTE_CHARS)
        self.assertLessEqual(sum(len(w) for w in got), tasks.WROTE_CHARS)
        self.assertTrue(got[-1].startswith("Line 29"))        # the newest is kept

    def test_an_unchanged_stretch_costs_nothing_the_second_time(self):
        ask = FakeAsk(REPLY)
        first = tasks.run(doc(), world(), ask, events=[])
        second = tasks.run(doc(), world(), ask, events=[])
        self.assertEqual(len(ask.calls), 1)
        self.assertTrue(second.get("cached"))
        self.assertEqual(len(second["tasks"]), len(first["tasks"]))
        tasks.run(doc(), world(), ask, events=[], force=True)
        self.assertEqual(len(ask.calls), 2)

    def test_the_estimate_is_reported(self):
        result = tasks.run(doc(), world(), FakeAsk(REPLY), dry_run=True, events=[])
        self.assertGreater(result["estimate"], labels.OVERHEAD_TOKENS)


if __name__ == "__main__":
    unittest.main()
