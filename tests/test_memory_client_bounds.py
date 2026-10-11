import concurrent.futures,tempfile,unittest
from unittest.mock import patch,MagicMock
from memory_client import MemoryClient
class HeldExecutor:
    def submit(self,*args):return concurrent.futures.Future()
    def shutdown(self,**kwargs):pass
class BoundsTests(unittest.TestCase):
    def test_unconsumed_requests_are_bounded(self):
        c=MemoryClient('/tmp/unused');c.executor.shutdown();c.controls.shutdown();c.executor=HeldExecutor();c.controls=HeldExecutor();c.started=True
        for i in range(100):c.request('get_project_context',{'project_id':'p'},i)
        self.assertEqual(len(c.poll()),92)
        c.stop()
    def test_failed_start_closes_control_pipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=MemoryClient(tmp);process=MagicMock();process.poll.return_value=1
            with patch('memory_client.subprocess.Popen',return_value=process):c._start()
            try:self.assertIsNone(c.control)
            finally:c.stop()
    def test_explicit_retry_after_transient_start_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=MemoryClient(tmp)
            with patch('memory_client.subprocess.Popen',side_effect=OSError('transient')) as spawn:
                c.start();c.executor.submit(lambda:None).result(2)
                c.retry();c.executor.submit(lambda:None).result(2)
                self.assertEqual(spawn.call_count,2)
            c.stop()
    def test_child_exit_invalidates_state_and_allows_explicit_retry(self):
        c=MemoryClient('/tmp/unused');c.started=True;c.capability='old';c.ready.set()
        c.process=MagicMock();c.process.poll.return_value=1
        events=c.poll()
        self.assertIsNone(c.capability);self.assertTrue(any(e['type']=='error' for e in events))
        with patch.object(c,'start') as start:c.retry();start.assert_called_once()
        c.stop()
