"""Real socket framing refuses malformed/oversized requests without allocation."""
import socket
import struct
import unittest
from semantic_memory import ipc


class FrameTests(unittest.TestCase):
    def test_length_prefixed_json_round_trip(self):
        a,b=socket.socketpair();self.addCleanup(a.close);self.addCleanup(b.close)
        payload={'version':1,'method':'query','params':{'query':'café'}}
        ipc.send_frame(a,payload)
        self.assertEqual(ipc.read_frame(b),payload)

    def test_oversized_and_malformed_frames_are_rejected(self):
        for raw in (struct.pack('!I',65537),struct.pack('!I',1)+b'[',struct.pack('!I',2)+b'[]'):
            a,b=socket.socketpair()
            try:
                a.sendall(raw);a.shutdown(socket.SHUT_WR)
                with self.assertRaises(ValueError):ipc.read_frame(b)
            finally:a.close();b.close()


class SupervisorTests(unittest.TestCase):
    def test_child_exits_on_parent_control_eof_and_socket_is_private(self):
        import os
        import subprocess
        import sys
        import tempfile
        import time
        from pathlib import Path
        from semantic_memory.live_bridge import read_private_json
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)/'memory';read_fd,write_fd=os.pipe()
            proc=subprocess.Popen([sys.executable,'scripts/project_memory_service.py','--data-dir',str(data),'--control-fd',str(read_fd),'--headless'],pass_fds=(read_fd,),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            os.close(read_fd)
            try:
                deadline=time.monotonic()+10
                while not (data/'service.json').exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(0.02)
                self.assertTrue((data/'service.json').exists(), 'Service failed to publish readiness')
                info=read_private_json(data/'service.json');path=Path(info['socket'])
                self.assertEqual(path.stat().st_mode&0o777,0o600)
                self.assertEqual(path.parent.stat().st_mode&0o777,0o700)
                caps=read_private_json(data/'capabilities.json')
                self.assertEqual(ipc.request(data/'service.json',caps['owner'],'status',{})['state'],'Disabled')
                os.close(write_fd);write_fd=None
                self.assertEqual(proc.wait(timeout=10),0)
                self.assertFalse(path.exists())
                self.assertFalse((data/'service.json').exists())
            finally:
                if write_fd is not None:os.close(write_fd)
                if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
                proc.stderr.close()

    def test_native_client_start_and_requests_complete_asynchronously(self):
        import tempfile
        import time
        from pathlib import Path
        from memory_client import MemoryClient
        with tempfile.TemporaryDirectory() as tmp:
            client=MemoryClient(Path(tmp)/'memory',headless=True)
            try:
                started=time.monotonic();client.start()
                self.assertLess(time.monotonic()-started,.25)
                client.request('status',{},'status-1')
                deadline=time.monotonic()+10;responses=[]
                while time.monotonic()<deadline:
                    responses.extend(client.poll())
                    if any(v.get('id')=='status-1' for v in responses):break
                    time.sleep(.02)
                response=next(v for v in responses if v.get('id')=='status-1')
                self.assertEqual(response['result']['state'],'Disabled')
            finally:
                client.stop()
                if client.process:client.process.wait(timeout=10)

    def test_pause_is_not_queued_behind_a_slow_query(self):
        import tempfile
        import threading
        import time
        from pathlib import Path
        from unittest.mock import patch
        from memory_client import MemoryClient
        from semantic_memory.service import MemoryService
        with tempfile.TemporaryDirectory() as tmp:
            service=MemoryService(Path(tmp)/'memory',focus_provider=lambda:None)
            server=ipc.PrivateServer(service)
            client=MemoryClient(service.directory,headless=True);client.started=True;client.capability=service.owner_capability
            entered=threading.Event();release=threading.Event();actual=service.serve_request
            def delayed(cap,method,params):
                if method=='status':entered.set();release.wait(3)
                return actual(cap,method,params)
            try:
                with patch.object(service,'serve_request',side_effect=delayed):
                    client.request('status',{},'slow')
                    self.assertTrue(entered.wait(1))
                    client.request('pause',{},'pause')
                    deadline=time.monotonic()+1;events=[]
                    while time.monotonic()<deadline:
                        events.extend(client.poll())
                        if any(e.get('id')=='pause' for e in events):break
                        time.sleep(.01)
                    self.assertTrue(any(e.get('id')=='pause' and not e.get('error') for e in events))
            finally:
                release.set();client.stop();server.close();service.close()
