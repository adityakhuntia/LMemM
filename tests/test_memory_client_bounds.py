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
