"""Explicit offline legacy-data import with a private backup and atomic publish."""
import os
import shutil
import tempfile
from pathlib import Path


def import_legacy_data(source,target):
    source=Path(source);target=Path(target)
    if source.is_symlink() or not source.is_dir() or not (source/'memory/memory.json').is_file():
        raise ValueError('Choose the legacy LMemM data directory containing memory/memory.json')
    if target.is_symlink() or target.exists():raise ValueError('Destination already exists; preserve it and choose a fresh destination')
    if (source/'.lmemm.pid').exists() or (source.parent/'.lmemm.pid').exists():
        raise ValueError('Stop the old LMemM session and remove a stale PID file before importing')
    for path in source.rglob('*'):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):raise ValueError('Legacy data contains a symlink or unsupported file')
    target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if source.resolve()==target.parent.resolve() or source.resolve() in target.resolve().parents:
        raise ValueError('Import destination must be outside the old data directory')
    stage=Path(tempfile.mkdtemp(prefix='.lmemm-import-',dir=target.parent))
    backup=target.parent/('legacy-backup-'+os.urandom(8).hex())
    try:
        shutil.copytree(source,backup)
        shutil.copytree(backup,stage,dirs_exist_ok=True)
        for base in (backup,stage):
            base.chmod(0o700)
            for path in base.rglob('*'):path.chmod(0o700 if path.is_dir() else 0o600)
        # A running endpoint/old source-sharing token is not an imported permission.
        for name in ('service.json','capabilities.json','browser-host.json'):
            (stage/'semantic'/name).unlink(missing_ok=True)
        for name in ('clients','bridge'):
            path=stage/'semantic'/name
            if path.is_dir():shutil.rmtree(path)
        os.replace(stage,target)
        return {'destination':str(target),'backup':str(backup)}
    finally:
        if stage.exists():shutil.rmtree(stage)
