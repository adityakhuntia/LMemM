#!/usr/bin/env python3
"""Standalone opt-in project-memory pilot; never starts a model service."""
import argparse
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from semantic_memory.live_pilot import Pilot,inspect_project
from semantic_memory.live_bridge import read_private_json,write_private_json


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--data-dir',type=Path,required=True)
 sub=parser.add_subparsers(dest='command',required=True)
 start=sub.add_parser('start');start.add_argument('--workspace',type=Path,action='append',required=True)
 start.add_argument('--runtime-config',type=Path);start.add_argument('--experimental-model',action='store_true')
 for name in ('status','pause','resume','flush','stop'):sub.add_parser(name)
 query=sub.add_parser('context');query.add_argument('--project',type=Path,required=True);query.add_argument('--days',type=int,default=2);query.add_argument('--json',action='store_true')
 delete=sub.add_parser('delete-session');delete.add_argument('--session',required=True);delete.add_argument('--confirm',action='store_true')
 args=parser.parse_args()
 if args.data_dir.is_symlink():raise ValueError("Symlink pilot directory forbidden")
 directory=args.data_dir.resolve()
 if args.command=='context':
  result=inspect_project(directory/'memory.sqlite',args.project,args.days)
  if args.json:print(json.dumps(result,indent=2,ensure_ascii=False));return
  print('Experimental project recall — source snapshots do not establish completed work.')
  print('Coverage:',json.dumps(result['coverage']))
  for heading,key in [('Observed source content','observed_sources'),('Recorded decisions','decisions'),('Recorded open tasks','open_tasks'),('Tentative interpretations','tentative')]:
   print('\n'+heading)
   for row in result[key]:
    print(row.get('at',''),row.get('text',row.get('statement','')))
    print('  File:',row.get('locator',''))
    print('  Source:',row.get('id',''),row.get('citations',''))
  return
 if args.command=='status':print(json.dumps(read_private_json(directory/'status.json'),indent=2));return
 if args.command=='delete-session':
  status=read_private_json(directory/'status.json')
  if not status['closed']:raise ValueError('Stop the pilot before deleting a session')
  from semantic_memory.store import SemanticStore
  from semantic_memory.retention import delete_session
  store=SemanticStore(directory/'memory.sqlite')
  try:
   count=store.connection.execute('SELECT count(*) FROM sources WHERE session_id=?',(args.session,)).fetchone()[0]
   if args.confirm:print(delete_session(store,args.session));store.connection.execute('VACUUM')
   else:print(f'{count} sources selected. Add --confirm to delete this session and dependent memories.')
  finally:store.close()
  return
 if args.command!='start':
  status=read_private_json(directory/'status.json')
  if status['closed']:raise ValueError('Pilot is stopped')
  write_private_json(directory/'control.json',dict(session=status['session'],command=args.command));print('Control requested:',args.command);return
 if bool(args.runtime_config)!=args.experimental_model:raise ValueError('Supply both --runtime-config and --experimental-model for experimental inference')
 directory.mkdir(parents=True,exist_ok=True,mode=0o700)
 import fcntl
 lock=os.open(directory/'pilot.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
 try:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  factory=None
  if args.runtime_config:
   from semantic_memory.local_runtime import LocalRuntime,RuntimeConfig
   config=json.loads(args.runtime_config.read_text())
   runtime=RuntimeConfig(Path(config['executable']),Path(config['model_path']),tuple(config.get('arguments',())),config.get('context_limit',8192))
   factory=lambda:LocalRuntime(runtime)
  pilot=Pilot(directory,args.workspace,extractor_factory=factory)
  import AppKit
  import macos
  app=AppKit.NSApplication.sharedApplication();app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
  class Lifecycle:
   flags=set()
   def trigger(self,why):pass
   def set_flag(self,name,on):
    if on:
     self.flags.add(name);pilot.pause('System '+name)
    else:self.flags.discard(name)
  lifecycle=Lifecycle();events=macos.subscribe(lifecycle)
  print('Experimental pilot running. Grant:',pilot.bridge.directory/'grant.json')
  print('Connect the VS Code extension explicitly. Ctrl-C stops. Model:', 'experimental' if factory else 'evidence only')
  try:
   while True:
    macos.next_event(app,0.25)
    control=directory/'control.json'
    if control.exists():
     try:
      value=read_private_json(control);control.unlink()
      if value.get('session')==pilot.bridge.session:
       command=value.get('command')
       if command=='stop':break
       if command=='resume' and lifecycle.flags:print('Resume blocked by system state')
       elif command in ('pause','resume','flush'):
        try:getattr(pilot,command)()
        except RuntimeError as error:print(error)
     except (ValueError,OSError):control.unlink(missing_ok=True)
    pilot.tick()
  except KeyboardInterrupt:pass
  finally:pilot.close()
 finally:os.close(lock)

if __name__=='__main__':
 try:main()
 except (ValueError,OSError,RuntimeError) as error:sys.exit(str(error))
