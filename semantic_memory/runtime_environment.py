"""Keep alias-app workers in the repo venv and restarts in the native app."""
import os
from pathlib import Path
import sys

def python_executable():
    if getattr(sys,'frozen',False):
        python=Path(__file__).resolve().parents[1]/'.venv/bin/python'
        if python.is_file():return str(python)  # Resolving this symlink loses pyvenv.cfg.
        raise ValueError('The checkout virtual environment is missing. Rebuild LMemM after installing requirements.')
    return sys.executable

def launch_argv(arguments):
    native=os.environ.get('EXECUTABLEPATH')
    if getattr(sys,'frozen',False) and native and Path(native).is_file():
        return [native,*arguments]
    return [python_executable(),os.path.abspath(sys.argv[0]),*arguments]
