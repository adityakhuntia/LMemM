"""Keep alias-app workers in the repo venv and restarts in the native app."""
import os
from pathlib import Path
import sys


def standalone_resources():
    if not getattr(sys,'frozen',False):return None
    root=Path(os.environ.get('RESOURCEPATH',Path(sys.executable).parent.parent/'Resources'))
    return root if (root/'standalone.json').is_file() else None


def native_executable():
    native=Path(os.environ.get('EXECUTABLEPATH',Path(sys.executable).parent/'LMemM'))
    if not native.is_file():raise ValueError('LMemM app launcher is missing; reinstall the app')
    return str(native)


def worker_argv(mode,arguments=()):
    resources=standalone_resources()
    if resources:return [native_executable(),'--lmemm-worker',mode,*arguments]
    files={'memory-service':'scripts/project_memory_service.py','embedding-service':'scripts/local_embedding_server.py',
           'mcp':'scripts/project_memory_mcp.py','permission-probe':'scripts/probe_permissions.py','browser-host':'packaging/browser_host_main.py'}
    if mode not in files:raise ValueError('Unknown worker mode')
    return [python_executable(),str(Path(__file__).resolve().parents[1]/files[mode]),*arguments]

def python_executable():
    if getattr(sys,'frozen',False):
        if standalone_resources():raise ValueError('Use bundled worker entry points in the installed app')
        python=Path(__file__).resolve().parents[1]/'.venv/bin/python'
        if python.is_file():return str(python)  # Resolving this symlink loses pyvenv.cfg.
        raise ValueError('The checkout virtual environment is missing. Rebuild LMemM after installing requirements.')
    return sys.executable

def launch_argv(arguments):
    if standalone_resources():return [native_executable(),*arguments]
    native=os.environ.get('EXECUTABLEPATH')
    if getattr(sys,'frozen',False) and native and Path(native).is_file():
        return [native,*arguments]
    return [python_executable(),os.path.abspath(sys.argv[0]),*arguments]
