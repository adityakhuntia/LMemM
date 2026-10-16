#!/usr/bin/env python3
"""App-supervised private project-memory service. No implicit source enrollment."""
import argparse
import os
from pathlib import Path
import select
import signal
import sys
import time
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'src')]
# Started from LMemM.app, this process gets py2app's interpreter, whose path puts the base Python's packages first (they may
# lack PyObjC's ApplicationServices or Quartz). Prefer the repo's .venv, as packaging/app_main.py does for the app itself.
import glob
for _site in glob.glob(str(Path(__file__).resolve().parents[1]/'.venv'/'lib'/'python*'/'site-packages')):sys.path.insert(0,_site)
from semantic_memory.service import MemoryService
from semantic_memory.ipc import PrivateServer


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--control-fd',type=int,required=True)
    parser.add_argument('--headless',action='store_true',help='Test harness: no native intake')
    args=parser.parse_args();stopped=False
    def stop(*_):
        nonlocal stopped
        stopped=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    service=MemoryService(args.data_dir,focus_provider=(lambda:None) if args.headless else None)
    server=None;app=None;events=None
    try:
        if not args.headless:
            import AppKit,macos
            app=AppKit.NSApplication.sharedApplication();app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
            class Lifecycle:
                flags=service.system_flags
                def trigger(self,why):pass
                def set_flag(self,name,on):
                    if on:self.flags.add(name);service.pause('System '+name)
                    else:self.flags.discard(name)
            lifecycle=Lifecycle();events=macos.subscribe(lifecycle)
        server=PrivateServer(service)
        while not stopped:
            readable,_,_=select.select([args.control_fd],[],[],0)
            if readable and not os.read(args.control_fd,1024):break
            if app:macos.next_event(app,.25)
            else:time.sleep(.05)
            try:service.tick()
            except (OSError,RuntimeError,ValueError):service.pause('Memory needs attention')
    finally:
        if server:server.close()
        service.close();os.close(args.control_fd)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError):sys.exit('Project memory service unavailable')
