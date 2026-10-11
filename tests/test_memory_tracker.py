"""Native lifecycle sends service controls without starting memory during tests."""
import tempfile
import unittest
from unittest.mock import patch
import config
import tracker


class LifecycleClient:
    def __init__(self):self.calls=[];self.stopped=False
    def request(self,method,params,request_id):self.calls.append((method,params))
    def poll(self):return []
    def stop(self):self.stopped=True


class TrackerMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.paths=config.use_paths(self.tmp.name);self.paths.__enter__();self.addCleanup(self.paths.__exit__,None,None,None)
        self.tracker=tracker.Tracker(show_widget=False,trail=False)
        self.client=LifecycleClient();self.tracker.memory_client=self.client

    def test_pause_resume_and_system_lock_reach_memory_client(self):
        with patch.object(self.tracker,'publish_status'):
            self.tracker.set_manual_pause(True)
            self.tracker.set_manual_pause(False)
            self.tracker.set_flag('locked',True)
        self.assertEqual([m for m,_ in self.client.calls],['pause','resume','pause'])
        self.assertEqual(self.client.calls[-1][1]['reason'],'System locked')

    def test_normal_constructor_does_not_launch_service_or_enroll_sources(self):
        another=tracker.Tracker(show_widget=False,trail=False)
        self.assertIsNone(another.memory_client)
