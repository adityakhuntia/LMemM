"""Chrome native messaging host. stdout is exclusively framed protocol output."""
import json
import struct
import sys
from .live_bridge import read_private_json
from .ipc import request as service_request

MAX_MESSAGE=1048576


def _exact(stream,size):
    chunks=[]
    while size:
        chunk=stream.read(size)
        if not chunk:raise ValueError('Incomplete browser message')
        chunks.append(chunk);size-=len(chunk)
    return b''.join(chunks)


def read_message(stream):
    prefix=stream.read(4)
    if not prefix:return None
    if len(prefix)!=4:raise ValueError('Incomplete browser message')
    size=struct.unpack('=I',prefix)[0]
    if not 1<=size<=MAX_MESSAGE:raise ValueError('Browser message too large')
    value=json.loads(_exact(stream,size))
    if not isinstance(value,dict):raise ValueError('Browser object required')
    return value


def write_message(stream,value):
    raw=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
    if not 1<=len(raw)<=MAX_MESSAGE:raise ValueError('Browser response too large')
    stream.write(struct.pack('=I',len(raw)));stream.write(raw);stream.flush()


def forward(config_path,origin,message):
    config=read_private_json(config_path)
    if origin!='chrome-extension://'+config['extension_id']+'/':raise ValueError('Browser extension not paired')
    return service_request(config['service_file'],config['capability'],'browser_request',{'request':message},message.get('request_id'))


def main(config_path,origin):
    while True:
        message=read_message(sys.stdin.buffer)
        if message is None:return
        try:
            result=forward(config_path,origin,message)
            response={'request_id':message.get('request_id'),'ok':True,'result':result}
        except (OSError,ValueError,KeyError,TypeError):
            response={'request_id':message.get('request_id'),'ok':False,'error':{
                'code':'unavailable','message':'Save not confirmed. Open LMemM, resume Memory and check browser pairing and the destination project.'}}
        write_message(sys.stdout.buffer,response)
