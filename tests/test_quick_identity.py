"""Quick identity: knowing what you're on from metadata alone, before any OCR."""

import unittest

import identity
import understand


def meta(**kw):
    base = {"app": "Google Chrome", "bundle_id": "com.google.Chrome", "window": "x", "url": None,
            "site": None, "tab_title": None}
    base.update(kw)
    return base


def item(iid, st, last_seen="2026-10-08T10:00:00"):
    ref = understand.ref(st)
    return {"id": iid, "ref": ref, "refs": [ref], "last_seen": last_seen}


class QuickIdentityTests(unittest.TestCase):
    def test_a_page_is_known_from_its_url_and_title_alone(self):
        m = meta(url="https://example.com/pricing", site="example.com", tab_title="Pricing")
        st = identity.quick_state(m)
        self.assertIsNotNone(st)
        items = {"a": item("a", st)}
        self.assertEqual(identity.find_item(items, st), "a")

    def test_two_tabs_are_told_apart(self):
        a = identity.quick_state(meta(url="https://example.com/a", site="example.com", tab_title="A"))
        b = identity.quick_state(meta(url="https://example.com/b", site="example.com", tab_title="B"))
        items = {"a": item("a", a), "b": item("b", b)}
        self.assertEqual(identity.find_item(items, a), "a")
        self.assertEqual(identity.find_item(items, b), "b")

    def test_a_place_never_seen_has_no_item(self):
        st = identity.quick_state(meta(url="https://example.com/new", site="example.com", tab_title="New"))
        self.assertIsNone(identity.find_item({}, st))

    def test_the_latest_of_several_instances_wins(self):
        st = identity.quick_state(meta(url="https://example.com/a", site="example.com", tab_title="A"))
        items = {"old": item("old", st, "2026-10-08T09:00:00"), "new": item("new", st, "2026-10-08T11:00:00")}
        self.assertEqual(identity.find_item(items, st), "new")

    def test_a_whatsapp_chat_needs_the_screen(self):
        m = meta(app="WhatsApp", bundle_id="net.whatsapp.WhatsApp", window="WhatsApp")
        self.assertIsNone(identity.quick_state(m))

    def test_a_page_from_its_url_and_window_title_finds_the_same_item_a_capture_made(self):
        captured = identity.quick_state(meta(url="https://rm.example.edu/portal/home", site="rm.example.edu",
                                             tab_title="Portal"))
        items = {"p": item("p", captured)}
        st = identity.page_state("Google Chrome", "https://rm.example.edu/portal/home", "Portal - Google Chrome")
        self.assertEqual(identity.find_item(items, st), "p")

    def test_a_page_you_have_never_been_on_finds_nothing(self):
        st = identity.page_state("Google Chrome", "https://other.example.edu/", "Other - Google Chrome")
        self.assertIsNotNone(st)
        self.assertIsNone(identity.find_item({}, st))


if __name__ == "__main__":
    unittest.main()
