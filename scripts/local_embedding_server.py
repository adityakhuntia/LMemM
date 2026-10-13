#!/usr/bin/env python3
"""Own Ollama and reap it when its service parent closes the control pipe."""
import argparse,os,select,signal,subprocess
p=argparse.ArgumentParser();p.add_argument('--control-fd',type=int,required=True);p.add_argument('--models',required=True);p.add_argument('--ollama',required=True);p.add_argument('--pidfile');a=p.parse_args()
stopped=False
def stop(*args):
    global stopped
    stopped=True
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGHUP,stop)   # a closed terminal must not leave Ollama behind
env={**os.environ,'OLLAMA_NO_CLOUD':'1','OLLAMA_HOST':'127.0.0.1:11455','OLLAMA_MODELS':a.models,'OLLAMA_NUM_PARALLEL':'1','OLLAMA_MAX_LOADED_MODELS':'1'}
child=subprocess.Popen([a.ollama,'serve'],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
if a.pidfile:
    try:open(a.pidfile,'w').write(str(child.pid))
    except OSError:pass
try:
    while not stopped and child.poll() is None:
        ready,_,_=select.select([a.control_fd],[],[],.25)
        if ready and not os.read(a.control_fd,1024):break
finally:
    if a.pidfile:
        try:os.unlink(a.pidfile)
        except OSError:pass
    try:os.killpg(child.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:child.wait(3)
    except subprocess.TimeoutExpired:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait()
    os.close(a.control_fd)
