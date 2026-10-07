"""Run-scoped private visible-source protocol; never reads document contents."""
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, unquote
from .contracts import SourceEnvelope, TextSpan
from .policy import identifier

EXCLUDED={'node_modules','vendor','dist','build','__pycache__','credentials','secrets'}

def read_private_json(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        s=os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode & 0o777 != 0o600 or s.st_nlink!=1:
            raise ValueError('Non-private bridge file')
        data=os.read(fd,32769)
        if len(data)>32768: raise ValueError('Oversize bridge file')
        result=json.loads(data)
        if not isinstance(result,dict): raise ValueError('Object required')
        return result
    finally: os.close(fd)

def write_private_json(path,value):
    path=Path(path)
    temp=path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'w') as f: json.dump(value,f); f.flush(); os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)

def local_path(uri):
    p=urlsplit(uri)
    if p.scheme!='file' or p.netloc or p.query or p.fragment or '\x00' in unquote(p.path):
        raise ValueError('Local file required')
    return Path(unquote(p.path)).resolve(strict=True)

class Bridge:
    def __init__(self,directory,roots,clock=time.time):
        self.directory=Path(directory)
        self.roots=tuple(Path(r).resolve(strict=True) for r in roots)
        if not self.roots or any(not r.is_dir() for r in self.roots): raise ValueError('Workspace roots required')
        self.clock=clock; self.clients={}; self.last={}; self.revision=0; self.active=True
        self.session=secrets.token_hex(16); self.token=secrets.token_hex(32)
    def open_session(self):
        if self.directory.is_symlink(): raise ValueError('Symlink bridge')
        self.directory.mkdir(mode=0o700,parents=True,exist_ok=True)
        s=self.directory.stat()
        if s.st_uid!=os.getuid() or s.st_mode & 0o777 != 0o700: raise ValueError('Non-private directory')
        for name in ('events','acks'):
            p=self.directory/name
            p.mkdir(mode=0o700,exist_ok=True)
            if p.is_symlink() or p.stat().st_mode & 0o777 != 0o700: raise ValueError('Non-private directory')
        for name in ('events','acks'):
            for p in (self.directory/name).glob('*.json'):
                if re.fullmatch('[a-f0-9]{32}',p.stem):p.unlink()
        return self.publish_grant()
    def publish_grant(self):
        grant=dict(token=self.token,session=self.session,roots=[str(r) for r in self.roots],active=self.active,revision=self.revision)
        write_private_json(self.directory/'grant.json',grant)
        return grant
    def expire(self):
        expired=[]
        for client,value in list(self.clients.items()):
            if self.clock()-value['at']>2 or not (self.directory/'events'/(client+'.json')).exists():
                expired.append(client);del self.clients[client];self.last.pop(client,None)
                (self.directory/'acks'/(client+'.json')).unlink(missing_ok=True)
                (self.directory/'events'/(client+'.json')).unlink(missing_ok=True)
        return expired
    def accept(self,m,focus):
        try:
            if len(json.dumps(m,ensure_ascii=False).encode())>32768 or not self.active: return None
            if type(m.get('revision'))!=int or m['revision']!=self.revision: return None
            if not hmac.compare_digest(m['token'],self.token) or m['session']!=self.session: return None
            client=m['client']; seq=m['seq']; at=m['at']
            if not isinstance(client,str) or not re.fullmatch('[a-f0-9]{32}',client): return None
            if type(seq)!=int or seq<1 or type(at) not in (int,float) or not -0.25<=self.clock()-at<=2: return None
            old=self.clients.get(client)
            if old and seq<=old['seq']: return None
            if old and m['kind']=='heartbeat' and m.get('focused') is False:
                old.update(seq=seq,at=at,focused=False);self.last.pop(client,None);return None
            if focus is None:return None
            if m['kind']=='connect':
                if not re.search(r'(?<![a-f0-9])'+re.escape('LMemM '+client)+r'(?![a-f0-9])',focus.title): return None
                if old and (old['window']!=focus.window or old['pid']!=focus.pid): return None
                if m.get('focused') is not True or len(self.clients)>=8 and not old: return None
                self.clients[client]=dict(seq=seq,at=at,window=focus.window,pid=focus.pid,focused=True)
                write_private_json(self.directory/'acks'/(client+'.json'),dict(session=self.session,window=focus.window,seq=seq))
                return None
            if not old or m.get('window')!=old['window'] or focus.window!=old['window'] or focus.pid!=old['pid']: return None
            old.update(seq=seq,at=at,focused=m.get('focused') is True)
            if not old['focused']: self.last.pop(client,None); return None
            if sum(c['focused'] and self.clock()-c['at']<=2 and c['window']==focus.window for c in self.clients.values())!=1: return None
            if m['kind']=='heartbeat': return None
            if m['kind'] not in ('snapshot','note'): return None
            raw=Path(unquote(urlsplit(m['document']).path))
            root=local_path(m['workspace']); doc=local_path(m['document'])
            if raw != doc: return None
            if root not in self.roots or not doc.is_file(): return None
            relative=doc.relative_to(root)
            if any(part.startswith('.') or part.lower() in EXCLUDED for part in relative.parts): return None
            if doc.suffix.lower() in ('.pem','.key','.p12','.pfx'): return None
            spans=m['spans']
            if not isinstance(spans,list) or not 1<=len(spans)<=4: return None
            for s in spans:
                if not isinstance(s['text'],str) or len(s['text'].encode())>4096 or type(s.get('truncated',False))!=bool: return None
            if sum(len(s['text'].encode()) for s in spans)>16384: return None
            digest=hashlib.sha256(json.dumps([str(doc),spans,m['kind']],sort_keys=True).encode()).hexdigest()
            if self.last.get(client)==digest: return None
            self.last[client]=digest
            sid=identifier('source',self.session+client+str(seq))
            return SourceEnvelope(sid,datetime.fromtimestamp(at,timezone.utc).isoformat(),self.session,
                 'com.microsoft.VSCode',str(doc),str(root),True,
                 'user_note' if m['kind']=='note' else 'trusted_artifact_snapshot',
                 tuple(TextSpan(str(i),s['text'],s.get('truncated',False)) for i,s in enumerate(spans)),self.revision)
        except (KeyError,ValueError,TypeError,OSError,OverflowError): return None
