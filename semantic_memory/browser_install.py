"""Install the explicitly approved Chrome/Chromium host in the current user's home."""
import os
import shlex
from pathlib import Path
from .live_bridge import write_private_json

EXTENSION_ID='ieicfnnnmgighnijggfffeeclagbkfkn'
HOST_NAME='com.lmemm.browser'
BROWSERS={'Chrome':'Google/Chrome','Chromium':'Chromium','ChromeForTesting':'Google/ChromeForTesting'}


def install_browser_host(home,data_dir,*,browser='Chrome',command=None):
    if browser not in BROWSERS:raise ValueError('Unsupported browser')
    support=Path(home)/'Library/Application Support'
    private=support/'LMemM'
    if private.is_symlink():raise ValueError('Private browser host directory required')
    private.mkdir(parents=True,mode=0o700,exist_ok=True)
    if private.stat().st_uid!=os.getuid() or private.stat().st_mode&0o777!=0o700:
        raise ValueError('Browser host directory must be private (0700)')
    if command is None:
        from .runtime_environment import worker_argv
        command=worker_argv('browser-host')
    # A small executable wrapper keeps manifest paths free of embedded arguments.
    host=private/'browser-host'
    temp=host.with_name(host.name+'.tmp-'+os.urandom(8).hex())
    fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o700)
    try:
        with os.fdopen(fd,'w') as stream:
            args=[*command,'--config',str(Path(data_dir)/'browser-host.json')]
            stream.write('#!/bin/sh\nexec '+shlex.join(args)+' "$@"\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temp,host)
    finally:temp.unlink(missing_ok=True)
    directory=support/BROWSERS[browser]/'NativeMessagingHosts'
    directory.mkdir(parents=True,exist_ok=True)
    manifest=directory/(HOST_NAME+'.json')
    write_private_json(manifest,dict(name=HOST_NAME,description='LMemM explicit project saves',
        path=str(host),type='stdio',allowed_origins=['chrome-extension://'+EXTENSION_ID+'/']))
    return {'manifest':str(manifest),'host':str(host),'extension_id':EXTENSION_ID}
