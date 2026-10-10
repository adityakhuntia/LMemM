"""capture_plan.py and labels.LiveLabeller: the speed rules, with fake clocks and no macOS or Claude."""

import tempfile
import unittest

import config
import capture_plan as cp
import labels
from test_labels import FakeProvider, excerpt, thing


class WindowsTest(unittest.TestCase):
    def test_own_windows_are_left_out_in_order(self):
        infos = [{"kCGWindowNumber": 5, "kCGWindowOwnerPID": 10}, {"kCGWindowNumber": 6, "kCGWindowOwnerPID": 99},
                 {"kCGWindowOwnerPID": 3}, {"kCGWindowNumber": 7, "kCGWindowOwnerPID": 3}]
        self.assertEqual(cp.windows_except_pid(infos, 99), [5, 7])
        self.assertEqual(cp.windows_except_pid(None, 1), [])


class BrowserCacheTest(unittest.TestCase):
    def setUp(self):
        self.t = [0.0]
        self.cache = cp.BrowserInfoCache(ttl=10, clock=lambda: self.t[0], max_entries=2)
        self.asked = 0

    def fetch(self, value):
        def go():
            self.asked += 1
            return value
        return go

    def test_asks_once_within_ttl_then_again(self):
        good = ("https://a.com/x", "A", False)
        self.assertEqual(self.cache.get("k", self.fetch(good)), good)
        self.t[0] = 9
        self.cache.get("k", self.fetch(good))
        self.assertEqual(self.asked, 1)
        self.t[0] = 11
        self.cache.get("k", self.fetch(good))
        self.assertEqual(self.asked, 2)

    def test_a_failed_lookup_is_not_cached(self):
        self.cache.get("k", self.fetch((None, None, False)))
        self.cache.get("k", self.fetch((None, None, False)))
        self.assertEqual(self.asked, 2)

    def test_a_different_title_is_a_different_key_and_size_is_capped(self):
        for key in ("a", "b", "c"):
            self.t[0] += 1
            self.cache.get(key, self.fetch(("u", "t", False)))
        self.assertEqual(len(self.cache.data), 2)
        self.assertNotIn("a", self.cache.data)


class TimingsTest(unittest.TestCase):
    def test_p95_and_max(self):
        t = cp.Timings(100)
        self.assertIsNone(t.p95())
        for ms in range(1, 101):
            t.add(ms)
        self.assertEqual(t.max(), 100)
        self.assertEqual(t.p95(), 96)
        self.assertEqual(t.count(), 100)


class LiveLabellerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        ctx = config.use_paths(self.tmp.name)
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        self.addCleanup(self.tmp.cleanup)
        self.t = [0.0]
        self.said = []
        self.paused = False
        self.items = {f"i{n}": thing(f"i{n}", title=f"Doc {n}", seconds=300, last="2026-10-06T10:00:00",
                            excerpts=[excerpt(f"A real sentence about topic {n} that is long enough to count.")])
                      for n in range(4)}
        self.provider = FakeProvider()

    def make(self, **kw):
        return labels.LiveLabeller(lambda: self.items, self.provider, say=self.said.append, paused=lambda: self.paused,
                                   first_after=100, every=500, min_waiting=3, clock=lambda: self.t[0], threaded=False,
                                   governor=labels.Governor(cap=50000), **kw)

    def test_waits_for_the_first_delay_then_runs_and_reports(self):
        live = self.make()
        self.assertFalse(live.poll())
        self.t[0] = 101
        self.assertTrue(live.poll())
        self.assertEqual(len(self.provider.calls), 1)
        self.assertTrue(any("labels:" in m for m in self.said))
        self.assertFalse(live.poll())               # next run is `every` later
        self.assertFalse(live.busy)

    def test_does_not_run_while_paused_and_keeps_waiting(self):
        live = self.make()
        self.t[0] = 101
        self.paused = True
        self.assertFalse(live.poll())
        self.paused = False
        self.assertTrue(live.poll())

    def test_too_few_waiting_makes_no_call(self):
        self.items = dict(list(self.items.items())[:2])
        live = self.make()
        self.t[0] = 101
        live.poll()
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(live.last["waiting"], 2)

    def test_an_expired_login_says_how_to_fix_it_and_backs_off(self):
        self.provider.error = labels.ProviderError(labels.LOGIN_HELP)
        live = self.make()
        self.t[0] = 101
        live.poll()
        self.assertTrue(any("/login" in m for m in self.said))
        self.t[0] = 101 + 600
        self.assertFalse(live.poll())

    def test_login_failures_from_the_cli_are_recognised(self):
        out = '{"type":"result","is_error":true,"result":"Failed to authenticate: OAuth session expired"}'
        cli = labels.ClaudeCli(runner=lambda *a, **k: type("D", (), {"returncode": 1, "stdout": out, "stderr": ""})(),
                               which=lambda n: "/x/claude")
        with self.assertRaises(labels.ProviderError) as ctx:
            cli.label("p", {"1"})
        self.assertEqual(str(ctx.exception), labels.LOGIN_HELP)

    def test_a_provider_crash_never_escapes(self):
        self.provider.error = RuntimeError("boom")
        live = self.make()
        self.t[0] = 101
        live.poll()
        self.assertIn("boom", live.last["stopped"])
        self.assertFalse(live.busy)


if __name__ == "__main__":
    unittest.main()
