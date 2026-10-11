"""Private local JSON transport with strict length and envelope validation."""
import json
import socket
import struct
from .live_bridge import read_private_json

MAX_FRAME=65536


def _exact(sock,size):
    chunks=[]
    while size:
        data=sock.recv(size)
        if not data:raise ValueError('Incomplete memory frame')
        chunks.append(data);size-=len(data)
    return b''.join(chunks)


def read_frame(sock):
    size=struct.unpack('!I',_exact(sock,4))[0]
    if not 1<=size<=MAX_FRAME:raise ValueError('Invalid memory frame length')
    value=json.loads(_exact(sock,size))
    if not isinstance(value,dict):raise ValueError('Memory object required')
    return value


def send_frame(sock,value):
    raw=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    if not 1<=len(raw)<=MAX_FRAME:raise ValueError('Invalid memory frame length')
    sock.sendall(struct.pack('!I',len(raw))+raw)


def request(info_path,capability,method,params,request_id=None):
    info=read_private_json(info_path)
    if info.get('version')!=1:raise ValueError('Unsupported memory service')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.settimeout(35);sock.connect(info['socket'])
        send_frame(sock,{'version':1,'capability':capability,'method':method,'params':params,'id':request_id})
        result=read_frame(sock)
    if result.get('version')!=1 or result.get('id')!=request_id:raise ValueError('Invalid memory response')
    if not result.get('ok'):raise ValueError(result.get('error','Service unavailable'))
    return result['result']


class PrivateServer:
    """Bounded request threads; native intake remains in the service main loop."""
    def __init__(self,service):
        import os
        import tempfile
        import threading
        from pathlib import Path
        from .live_bridge import write_private_json
        self.service=service;self.closed=threading.Event();self.slots=threading.BoundedSemaphore(4)
        self.directory=Path(tempfile.mkdtemp(prefix='lmemm-'))
        self.path=self.directory/'memory.sock'
        self.socket=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.socket.bind(str(self.path));os.chmod(self.path,0o600);self.socket.listen(4);self.socket.settimeout(.25)
        self.thread=threading.Thread(target=self._accept,daemon=True);self.thread.start()
        write_private_json(service.directory/'service.json',{'version':1,'socket':str(self.path),'pid':os.getpid()})

    def _accept(self):
        import threading
        while not self.closed.is_set():
            try:conn,_=self.socket.accept()
            except socket.timeout:continue
            except OSError:return
            if not self.slots.acquire(blocking=False):conn.close();continue
            threading.Thread(target=self._handle,args=(conn,),daemon=True).start()

    def _handle(self,conn):
        identifier=None
        try:
            conn.settimeout(35);value=read_frame(conn)
            if set(value)!={'version','capability','method','params','id'} or type(value['version']) is not int or value['version']!=1:
                raise ValueError('Invalid memory envelope')
            identifier=value['id']
            if identifier is not None and (not isinstance(identifier,str) or len(identifier.encode())>256):raise ValueError('Invalid request ID')
            result=self.service.serve_request(value['capability'],value['method'],value['params'])
            if self.closed.is_set():raise ValueError('unavailable')
            send_frame(conn,{'version':1,'id':identifier,'ok':True,'result':result})
        except Exception:
            try:send_frame(conn,{'version':1,'id':identifier,'ok':False,'error':'Service unavailable or request not permitted'})
            except (OSError,ValueError):pass
        finally:conn.close();self.slots.release()

    def close(self):
        self.closed.set();self.socket.close();self.thread.join(1)
        self.path.unlink(missing_ok=True);self.directory.rmdir()
        (self.service.directory/'service.json').unlink(missing_ok=True)
