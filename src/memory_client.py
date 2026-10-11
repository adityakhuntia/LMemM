"""Asynchronous native facade; UI polls completions and never waits on models."""
import concurrent.futures
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time


class MemoryClient:
    def __init__(self,data_dir,*,headless=False):
        self.directory=Path(data_dir);self.headless=headless;self.process=None;self.control=None
        self.capability=None;self.events=queue.SimpleQueue();self.stopping=False
        self.executor=concurrent.futures.ThreadPoolExecutor(max_workers=1,thread_name_prefix='memory-client')
        self.started=False;self.ready=threading.Event()
        self.controls=concurrent.futures.ThreadPoolExecutor(max_workers=1,thread_name_prefix='memory-control')

    def start(self):
        if self.started:return
        self.started=True;self.executor.submit(self._start)

    def _start(self):
        from semantic_memory.live_bridge import read_private_json
        try:
            if self.stopping:return
            read_fd,write_fd=os.pipe();self.control=write_fd
            script=Path(__file__).resolve().parents[1]/'scripts/project_memory_service.py'
            args=[sys.executable,str(script),'--data-dir',str(self.directory),'--control-fd',str(read_fd)]
            if self.headless:args.append('--headless')
            try:self.process=subprocess.Popen(args,pass_fds=(read_fd,),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            finally:os.close(read_fd)
            deadline=time.monotonic()+10
            info=self.directory/'service.json'
            while time.monotonic()<deadline and not self.stopping:
                if self.process.poll() is not None:raise RuntimeError('Service unavailable')
                try:
                    value=read_private_json(info)
                    if value['pid']==self.process.pid:
                        self.capability=read_private_json(self.directory/'capabilities.json')['owner']
                        self.ready.set();self.events.put({'type':'ready'});return
                except (OSError,ValueError,KeyError):pass
                time.sleep(.02)
            raise RuntimeError('Service startup unavailable')
        except Exception:
            self.ready.set();self.events.put({'type':'error','error':'Project memory service unavailable'})

    def request(self,method,params,request_id):
        if not self.started:self.start()
        if not self.stopping:
            executor=self.controls if method in {'pause','resume','revoke_agent','revoke_project','begin_note_mutation','reconcile_notes'} else self.executor
            executor.submit(self._request,method,params,request_id)

    def _request(self,method,params,request_id):
        from semantic_memory.ipc import request
        try:
            if not self.capability:self.ready.wait(10)
            if not self.capability or self.stopping:raise ValueError('Service unavailable')
            value=request(self.directory/'service.json',self.capability,method,params,request_id)
            self.events.put({'type':'response','id':request_id,'method':method,'result':value})
        except Exception:self.events.put({'type':'response','id':request_id,'method':method,'error':'Project memory unavailable'})

    def poll(self):
        values=[]
        while not self.events.empty():values.append(self.events.get())
        return values

    def stop(self):
        if self.stopping:return
        self.stopping=True;self.ready.set()
        if self.control is not None:
            try:os.close(self.control)
            except OSError:pass
            self.control=None
        self.executor.shutdown(wait=False,cancel_futures=True)
        self.controls.shutdown(wait=False,cancel_futures=True)
        process=self.process
        if process:
            def reap():
                try:process.wait(3)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:process.wait(3)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
            threading.Thread(target=reap,name='memory-stop',daemon=True).start()
