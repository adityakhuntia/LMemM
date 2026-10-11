"""LMemM - one folder of data per run, so each test run's memory stays separate. Plain functions.

Every `lmemm.py start` writes into its own folder under data/runs/:

    data/runs/#PR25|2026-10-12|Session 1/       memory/memory.json, sessions, trail, screenshots ...
    data/runs/#PR25|2026-10-12|Session 2/       the next start on the same day
    data/runs/#PR26|2026-10-13|Session 1/       a new PR or a new day starts again at 1

What every run shares, so a new run does not ask you to set up again or reset the day's token cap:
the setup state (data/onboarding.json), the daily token count (data/memory/labels_usage.json) and the "user" block of
memory.json, which is copied into each new run. Other commands (memory, tasks, brief, ask ...) read the latest run, or
the one named with `--run NAME`. The PR number comes from `--pr N`, the LMEMM_PR variable, or `gh pr view`.
"""

import json
import os
import re
import subprocess
from dataclasses import replace
from datetime import datetime

import config

RUNS = "runs"
MARKER = "run.json"


def runs_dir(base=None):
    return os.path.join(base or config.paths().data_dir, RUNS)


def pr_number(explicit=None, cwd=None):
    """The PR this run is for: --pr, else LMEMM_PR, else the open PR of the current branch (gh), else None."""
    for value in (explicit, os.environ.get("LMEMM_PR")):
        digits = re.sub(r"\D", "", str(value or ""))
        if digits:
            return digits
    try:
        out = subprocess.run(["gh", "pr", "view", "--json", "number", "-q", ".number"], cwd=cwd, capture_output=True,
                             text=True, timeout=6).stdout.strip()
        if out.isdigit():
            return out
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def folder_name(pr, day, session):
    return f"#PR{pr or 'x'}|{day}|Session {session}"


def next_name(base, pr, now=None):
    """The next free name for this PR and day: Session 1, 2, 3 ..."""
    day = (now or datetime.now()).strftime("%Y-%m-%d")
    stem = folder_name(pr, day, "")
    taken = [int(m.group(1)) for d in (os.listdir(runs_dir(base)) if os.path.isdir(runs_dir(base)) else [])
             if d.startswith(stem) and (m := re.search(r"Session (\d+)$", d))]
    return folder_name(pr, day, max(taken, default=0) + 1)


def latest(base=None):
    """The newest run folder (by the time written in its run.json), or None."""
    root = runs_dir(base)
    best = None
    for name in os.listdir(root) if os.path.isdir(root) else []:
        try:
            with open(os.path.join(root, name, MARKER)) as fh:
                made = json.load(fh)["started"]
        except (OSError, ValueError, KeyError):
            continue
        if best is None or made > best[0]:
            best = (made, os.path.join(root, name))
    return best[1] if best else None


def find(name, base=None):
    """A run folder by its full name, or by a unique part of it ('PR25', 'Session 2')."""
    root = runs_dir(base)
    names = sorted(os.listdir(root)) if os.path.isdir(root) else []
    exact = [n for n in names if n == name]
    part = exact or [n for n in names if name.lower() in n.lower()]
    if len(part) != 1:
        raise ValueError(f"No single run matches '{name}'. Runs: " + (", ".join(names) or "none yet"))
    return os.path.join(root, part[0])


def _user_block(base):
    try:
        with open(os.path.join(base, "memory", "memory.json")) as fh:
            doc = json.load(fh)
        return doc.get("user") if isinstance(doc, dict) and isinstance(doc.get("user"), dict) else None
    except (OSError, ValueError):
        return None


def use(folder, base):
    """Point every module at this run's folder; setup state and the token count stay in `base`."""
    config.PATHS = replace(config.PATHS, data_dir=folder, base_dir=base)


def begin(pr=None, now=None, cwd=None):
    """Make the next run folder, seed it with the user block, and switch to it. Returns its path."""
    now = now or datetime.now()
    base = config.paths().base_dir or config.paths().data_dir
    pr = pr_number(pr, cwd)
    folder = os.path.join(runs_dir(base), next_name(base, pr, now))
    os.makedirs(os.path.join(folder, "memory"), exist_ok=True)
    with open(os.path.join(folder, MARKER), "w") as fh:
        json.dump({"started": now.isoformat(timespec="seconds"), "pr": pr}, fh)
    user = _user_block(base) or _user_block(latest(base) or "")
    if user:
        with open(os.path.join(folder, "memory", "memory.json"), "w") as fh:
            json.dump({"schema_version": 1, "things": [], "items": [], "user": user}, fh)
    use(folder, base)
    return folder


def resume(name=None):
    """Carry on in an earlier run's folder (the latest, or the one `name` finds) instead of starting an empty one.
    ValueError when there is none to continue."""
    base = config.paths().base_dir or config.paths().data_dir
    folder = find(name, base) if name and name != "latest" else latest(base)
    if not folder:
        raise ValueError("No earlier run to continue. Start one without --continue first.")
    use(folder, base)
    return folder


def select(args):
    """For the commands that read memory: switch to the run named with `--run NAME` (removed from `args`), else the
    latest run, else stay on the data folder as it is. ValueError when the name matches no single run."""
    base = config.paths().base_dir or config.paths().data_dir
    folder = None
    if "--run" in args:
        i = args.index("--run")
        if i + 1 >= len(args):
            raise ValueError("--run needs a name, for example --run PR25")
        folder = find(args[i + 1], base)
        del args[i:i + 2]
    folder = folder or latest(base)
    if folder:
        use(folder, base)
    return folder
