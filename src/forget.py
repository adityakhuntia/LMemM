"""LMemM - delete everything it has kept. Backs `lmemm.py delete-all`, the promise on the setup
screens: "Delete it any time."

It removes what is inside LMemM's own data directory (screenshots, memory, sessions, the setup
record) and nothing outside it. It refuses while LMemM is running, and refuses a data directory
that is not clearly LMemM's own (the root, a home folder, or one that does not exist yet).
"""

import os
import shutil


def _safe(data_dir):
    real = os.path.realpath(data_dir)
    home = os.path.realpath(os.path.expanduser("~"))
    return os.path.isdir(real) and real not in ("/", home) and len(real.split(os.sep)) > 2


def plan(data_dir):
    """What delete-all would remove: {"files": n, "bytes": n, "entries": [top-level names]}."""
    if not _safe(data_dir):
        raise ValueError(f"not a LMemM data directory: {data_dir}")
    files = size = 0
    for root, _dirs, names in os.walk(data_dir):
        for name in names:
            files += 1
            try:
                size += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return {"data_dir": data_dir, "files": files, "bytes": size, "entries": sorted(os.listdir(data_dir))}


def delete_all(data_dir, running_pid=None):
    """Remove everything inside the data directory (the directory itself stays). Returns the
    plan that was carried out. ValueError if LMemM is running or the directory is not safe."""
    if running_pid:
        raise ValueError(f"LMemM is running (pid {running_pid}). Stop it first: ./run.sh stop, or Ctrl-C.")
    done = plan(data_dir)
    for name in done["entries"]:
        path = os.path.join(data_dir, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    return done
