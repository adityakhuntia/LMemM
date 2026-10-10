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

    def test_off_limits_apps_never_enter_the_story(self):
        w = world()
        w["chatgpt"]["app"] = "WhatsApp"
        _p, ids = tasks.payload_for(doc(), w)
        self.assertNotIn("chatgpt", ids)


if __name__ == "__main__":
    unittest.main()
