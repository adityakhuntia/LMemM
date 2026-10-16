"""Asynchronous native facade; UI polls completions and never waits on models."""
import concurrent.futures
import os
from pathlib import Path
import queue
import stat
import subprocess
import sys
from semantic_memory.runtime_environment import python_executable
import threading
import time

STARTUP_TIMEOUT=45

def _private_log(directory):
    directory.mkdir(parents=True,mode=0o700,exist_ok=True)
    info=directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o777!=0o700:
        raise OSError('Private service directory required')
    fd=os.open(directory/'service.log',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1:
            raise OSError('Private service log required')
        os.fchmod(fd,0o600);os.ftruncate(fd,0)
        return fd
    except BaseException:
        os.close(fd);raise

class MemoryClient:
    def __init__(self,data_dir,*,headless=False):
        self.directory=Path(data_dir);self.headless=headless;self.process=None;self.control=None
        self.capability=None;self.events=queue.SimpleQueue();self.stopping=False
        self.executor=concurrent.futures.ThreadPoolExecutor(max_workers=1,thread_name_prefix='memory-client')
        self.started=False;self.failed=False;self.generation=0;self.state_lock=threading.RLock();self.ready=threading.Event()
        self.query_slots=threading.BoundedSemaphore(8);self.control_slots=threading.BoundedSemaphore(8)
        self.controls=concurrent.futures.ThreadPoolExecutor(max_workers=1,thread_name_prefix='memory-control')

    def start(self):
        with self.state_lock:
            if self.started or self.stopping:return
            self.started=True;self.failed=False;self.capability=None;self.ready.clear();self.generation+=1
            self.executor.submit(self._start)

    def retry(self):
        self._check_child()
        if not self.started and not self.stopping:self.start()

    def _check_child(self):
        with self.state_lock:
            if self.started and self.capability and self.process and self.process.poll() is not None:
                self._close_control();self.capability=None;self.started=False;self.failed=True;self.generation+=1
                self.events.put({'type':'error','error':'Project memory stopped. Refresh evidence to retry.'})

    def _start(self):
        from semantic_memory.live_bridge import read_private_json
        try:
            if self.stopping:return
            read_fd,write_fd=os.pipe();self.control=write_fd
            script=Path(__file__).resolve().parents[1]/'scripts/project_memory_service.py'
            args=[python_executable(),str(script),'--data-dir',str(self.directory),'--control-fd',str(read_fd)]
            if self.headless:args.append('--headless')
            try:
                # Keep the service's last words in a private log: the IPC layer hides errors by design, so this is how a failed start is diagnosed.
                try:
                    log=_private_log(self.directory)
                except OSError:log=subprocess.DEVNULL
                try:self.process=subprocess.Popen(args,pass_fds=(read_fd,),stdin=subprocess.DEVNULL,stdout=log,stderr=log)
                finally:
                    if log!=subprocess.DEVNULL:os.close(log)
            finally:os.close(read_fd)
            if self.stopping:
                self._close_control();self._reap(self.process);return
            deadline=time.monotonic()+STARTUP_TIMEOUT
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
            self._close_control()
            if self.process:self._reap(self.process)
            with self.state_lock:self.capability=None;self.started=False;self.failed=True
            self.ready.set();self.events.put({'type':'error','error':'Project memory service unavailable. Refresh evidence to retry.'})

    def request(self,method,params,request_id):
        self._check_child()
        if not self.started and not self.failed:self.start()
        if not self.stopping:
            control=method in {'pause','resume','revoke_agent','revoke_project','begin_note_mutation','reconcile_notes'}
            executor=self.controls if control else self.executor
            slots=self.control_slots if control else self.query_slots
            if not slots.acquire(blocking=False):
                self.events.put({'type':'response','id':request_id,'method':method,'error':'Memory is busy; try again'});return
            try:future=executor.submit(self._request,method,params,request_id,self.generation)
            except RuntimeError:
                slots.release();return
            future.add_done_callback(lambda _:slots.release())

    def _request(self,method,params,request_id,generation):
        from semantic_memory.ipc import request
        try:
            if not self.capability:self.ready.wait(STARTUP_TIMEOUT)
            if not self.capability or self.stopping or generation!=self.generation:raise ValueError('Service unavailable')
            value=request(self.directory/'service.json',self.capability,method,params,request_id)
            if generation==self.generation:self.events.put({'type':'response','id':request_id,'method':method,'result':value})
        except Exception:
            if generation==self.generation:self.events.put({'type':'response','id':request_id,'method':method,'error':'Project memory unavailable'})

    def poll(self):
        self._check_child()
        values=[]
        while not self.events.empty():values.append(self.events.get())
        return values

    def stop(self):
        if self.stopping:return
        self.stopping=True;self.ready.set()
        self._close_control()
        self.executor.shutdown(wait=False,cancel_futures=True)
        self.controls.shutdown(wait=False,cancel_futures=True)
        if self.process:self._reap(self.process)

    def _close_control(self):
        fd,self.control=self.control,None
        if fd is not None:
            try:os.close(fd)
            except OSError:pass

    @staticmethod
    def _reap(process):
        def reap():
            try:process.wait(3)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:process.wait(3)
                except subprocess.TimeoutExpired:process.kill();process.wait()
        threading.Thread(target=reap,name='memory-stop',daemon=True).start()
