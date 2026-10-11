"""memory_search, ask, brief, recap and the "from earlier" step. No macOS, no Claude (a fake provider)."""

import json
import unittest
from datetime import datetime, timedelta

import ask
import brief
import labels
import memory_search as ms
import nextsteps
import recap
from test_labels import TmpPaths, excerpt, thing

NOW = datetime(2026, 10, 11, 15, 0, 0)


def world():
    return {
        "sheet": thing("sheet", app="Google Docs", title="Outreach Tracker - Google Sheets", last="2026-10-10T16:00:00",
                       excerpts=[excerpt("Reply rate after seven days of silence was 31 percent across the first batch")]),
        "mail": thing("mail", app="Mail", title="Draft", last="2026-10-11T14:50:00",
                      excerpts=[excerpt("Trigger runs the sendDrafts function every morning at eight o'clock")]),
        "chat": thing("chat", app="ChatGPT", title="Follow up system", last="2026-10-11T14:55:00", note_texts=["check the trigger on weekdays"]),
    }


def wrote(text, item="chat", at=NOW - timedelta(minutes=2)):
    return {"kind": "wrote", "item": item, "app": "ChatGPT", "title": "Follow up system", "at": at, "text": text}


class FakeAsk:
    name = "fake"

    def __init__(self, reply):
        self.reply, self.calls = reply, []
        self.last_exchange = None

    def ask(self, payload, instruction=None, model=None, effort="low"):
        self.calls.append((payload, instruction, model, effort))
        return self.reply, {"input_tokens": 5, "cache_creation_input_tokens": 2500, "output_tokens": 60}


class SearchTests(TmpPaths):
    def test_the_figure_is_found_on_the_sheet_and_ranked_first(self):
        found = ms.pieces(world())
        hits = ms.search("what was the reply rate figure from the sheet yesterday", found, now=NOW)
        self.assertEqual(hits[0]["piece"]["item"], "sheet")
        self.assertIn("31 percent", hits[0]["piece"]["text"])

    def test_nothing_matching_gives_nothing(self):
        self.assertEqual(ms.search("quarterly budget forecast", ms.pieces(world()), now=NOW), [])

    def test_a_source_line_says_where_and_when(self):
        piece = ms.search("reply rate", ms.pieces(world()), now=NOW)[0]["piece"]
        self.assertEqual(ms.source_line(piece, NOW), "Google Docs · Outreach Tracker - Google Sheets · on screen · yesterday")


class EarlierTests(TmpPaths):
    def test_a_line_you_wrote_finds_the_matching_line_seen_elsewhere(self):
        items = world()
        found = ms.pieces(items) + [wrote("The trigger runs the sendDrafts function every morning")]
        hit = ms.earlier(found, items, "chat", NOW)
        self.assertEqual(hit["item"], "mail")
        self.assertIn("sendDrafts", hit["text"])

    def test_one_shared_word_is_not_enough_and_old_writing_is_ignored(self):
        items = world()
        found = ms.pieces(items) + [wrote("Remember to thank everyone about this trigger soon")]
        self.assertIsNone(ms.earlier(found, items, "chat", NOW))
        old = ms.pieces(items) + [wrote("The trigger runs the sendDrafts function every morning", at=NOW - timedelta(hours=2))]
        self.assertIsNone(ms.earlier(old, items, "chat", NOW))

    def test_it_becomes_a_step_that_goes_when_it_stops_being_true(self):
        items, doc = world(), nextsteps.empty()
        hit = {"text": "Trigger runs the sendDrafts function every morning", "from": "Mail · Draft", "item": "mail", "query": "x"}
        cand = nextsteps.earlier_candidate(hit, items)
        added = nextsteps.refresh(doc, items, {}, NOW, front_id="chat", extra=[cand])
        self.assertEqual([a["kind"] for a in added], ["earlier"])
        self.assertEqual(nextsteps.view(doc, items, NOW)["steps"][0]["detail"]["copy"], hit["text"])
        nextsteps.refresh(doc, items, {}, NOW, front_id="chat", extra=[])
        self.assertEqual(nextsteps.view(doc, items, NOW)["count"], 0)


class DemoTests(TmpPaths):
    def test_demo_steps_show_all_four_boxes_and_survive_a_refresh(self):
        items, doc = world(), nextsteps.empty()
        self.assertEqual(len(nextsteps.demo(doc, items, NOW)), 4)
        nextsteps.refresh(doc, items, {}, NOW, front_id="chat")
        kinds = [s["kind"] for s in nextsteps.view(doc, items, NOW)["steps"]]
        self.assertEqual(sorted(kinds), ["earlier", "hanging", "next", "resume"])
        self.assertEqual(len(nextsteps.demo(doc, items, NOW)), 4)         # a restart replaces them, never doubles them
        self.assertEqual(nextsteps.demo(nextsteps.empty(), {}, NOW), [])


class AskTests(TmpPaths):
    def test_it_answers_from_numbered_sources_and_lists_the_ones_used(self):
        found = ms.pieces(world())
        provider = FakeAsk(json.dumps({"answer": "31 percent [1]", "used": [1]}))
        out = ask.answer("what was the reply rate on the sheet", found, provider, labels.Governor())
        self.assertEqual(out["answer"], "31 percent [1]")
        self.assertIn("31 percent", out["sources"][0]["text"])
        self.assertTrue(out["asked"])
        self.assertIn("SOURCE 1", provider.calls[0][0])

    def test_no_match_means_no_call(self):
        provider = FakeAsk("{}")
        out = ask.answer("quarterly budget forecast", ms.pieces(world()), provider, labels.Governor())
        self.assertFalse(out["asked"])
        self.assertEqual(provider.calls, [])

    def test_a_used_up_day_makes_no_call(self):
        governor = labels.Governor()
        governor.doc["tokens"] = governor.cap
        provider = FakeAsk("{}")
        out = ask.answer("reply rate", ms.pieces(world()), provider, governor)
        self.assertEqual(provider.calls, [])
        self.assertIn("limit", out["answer"])

    def test_garbage_and_wild_source_numbers_are_tamed(self):
        found = ms.pieces(world())
        out = ask.answer("reply rate", found, FakeAsk(json.dumps({"answer": "x", "used": [9, "[1]", 1]})), labels.Governor())
        self.assertEqual([s["n"] for s in out["sources"]], [1])
        out = ask.answer("reply rate", found, FakeAsk("not json"), labels.Governor())
        self.assertEqual(out["answer"], "not json")


class BriefAndRecapTests(TmpPaths):
    def book(self):
        return {"s": {"at": "2026-10-11T14:00:00", "tasks": [
            {"title": "Build follow-up automation", "goal": "Reply after seven days", "stage": "Building", "open": "Check the trigger",
             "items": ["chat", "mail"], "seconds": 3600, "last_wrote": "The trigger runs every morning"}]},
            "t": {"at": "2026-10-10T14:00:00", "tasks": [{"title": "Plan outreach", "goal": "g", "stage": "Planning", "open": None,
                                                           "items": ["sheet"], "seconds": 600}]}}

    def test_the_brief_has_the_task_the_writing_the_windows_and_the_notes(self):
        items = world()
        text = brief.build(items, self.book(), "chat", ms.pieces(items) + [wrote("I want a reminder after seven days")], NOW)
        for part in ("Build follow-up automation", "Reply after seven days", "Check the trigger", "I want a reminder",
                     "ChatGPT: Follow up system", "check the trigger on weekdays"):
            self.assertIn(part, text)
        self.assertLessEqual(len(text), brief.BRIEF_CHARS + 2)

    def book_now(self):
        b = self.book()
        b["s"]["at"] = "2026-10-11T14:00:00"
        return b

    def test_claude_writes_the_brief_from_curated_evidence_without_code_noise(self):
        items = world()
        items["mail"]["content"]["excerpts"].append(excerpt("sig = repr( (window_model. signature(self.banner), page, self.flow_sig"))
        provider = FakeAsk("I'm building a follow-up automation that replies after seven days.\n- The trigger runs every morning.\nNext: check the trigger on weekdays.")
        text, tokens = brief.compose(items, self.book_now(), "chat", ms.pieces(items), provider, labels.Governor(), NOW)
        self.assertTrue(text.startswith("# Context from my Mac"))
        self.assertIn("follow-up automation", text)
        self.assertGreater(tokens, 0)
        sent = provider.calls[0][0]
        self.assertIn("Build follow-up automation", sent)
        self.assertNotIn("window_model", sent)

    def test_the_brief_falls_back_to_the_plain_one_when_the_day_is_spent(self):
        governor = labels.Governor()
        governor.doc["tokens"] = governor.cap
        provider = FakeAsk("x" * 100)
        text, tokens = brief.compose(world(), self.book_now(), "chat", [], provider, governor, NOW)
        self.assertEqual((provider.calls, tokens), ([], 0))
        self.assertIn("Build follow-up automation", text)

    def test_breadcrumbs_are_cut_from_what_you_wrote(self):
        self.assertEqual(ms.breadcrumb_off("script.google.com · Auto Send > Therefore emails are not scheduled"),
                         "Therefore emails are not scheduled")

    def test_no_things_means_no_brief(self):
        self.assertEqual(brief.build({}, {}, None, [], NOW), "")

    def test_the_recap_is_today_only_by_default_and_a_week_with_days(self):
        today = recap.build(self.book(), 1, NOW)
        self.assertIn("Build follow-up automation", today)
        self.assertNotIn("Plan outreach", today)
        self.assertIn("Plan outreach", recap.build(self.book(), 7, NOW))
        self.assertIn("Check the trigger", today)
        self.assertEqual(recap.build({}, 1, NOW), "")


if __name__ == "__main__":
    unittest.main()
