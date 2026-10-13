import concurrent.futures,tempfile,unittest
from unittest.mock import patch,MagicMock
from memory_client import MemoryClient
class HeldExecutor:
    def submit(self,*args):return concurrent.futures.Future()
    def shutdown(self,**kwargs):pass
class BoundsTests(unittest.TestCase):
    def test_service_log_cannot_truncate_a_symlink_target(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'memory';directory.mkdir(mode=0o700)
            target=Path(tmp)/'keep.txt';target.write_text('keep this')
            (directory/'service.log').symlink_to(target)
            c=MemoryClient(directory);self.addCleanup(c.stop)
            process=MagicMock();process.poll.return_value=1
            with patch('memory_client.subprocess.Popen',return_value=process):c._start()
            self.assertEqual(target.read_text(),'keep this')

    def test_controls_wait_for_the_full_service_startup_window(self):
        c=MemoryClient('/tmp/unused');self.addCleanup(c.stop)
        c.started=True;c.ready=MagicMock()
        c._request('pause',{},'pause-1',c.generation)
        self.assertGreaterEqual(c.ready.wait.call_args.args[0],45)

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
