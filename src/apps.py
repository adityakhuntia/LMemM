"""LMemM - which apps LMemM may look at.

First-run setup lets a person say "only in these apps". That choice is a list of bundle ids
(`watch_apps`, stored in the user block of memory.json). The rule is two lines:

    an empty list     every app is watched (the default)
    a non-empty list  only those apps are watched; every other app is skipped before anything
                      is captured, read or remembered, and an app that cannot be identified
                      is skipped too (the rule fails closed)

This file is plain Python with no PyObjC, so the rule and the installed-app scan are tested
everywhere. The icons come from macOS at draw time (onboarding_ui.py), not from here.
"""

import os
import plistlib

APP_DIRS = ("/Applications", "/Applications/Utilities", "/System/Applications",
            "/System/Applications/Utilities", "~/Applications")
HIDDEN_IDS = {"com.lmemm.listen"}          # LMemM's own helper is never offered
MAX_WATCHED = 500                          # more than any real person picks; bounds the stored list


def watched(watch_apps, bundle_id):
    """True when LMemM may look at the app with this bundle id. `watch_apps` is a list of
    {"id", "name"} entries (or bare ids); empty or None means every app."""
    ids = _ids(watch_apps)
    if not ids:
        return True
    return bool(bundle_id) and bundle_id in ids


def _ids(watch_apps):
    out = set()
    for entry in watch_apps or ():
        value = entry.get("id") if isinstance(entry, dict) else entry
        if isinstance(value, str) and value:
            out.add(value)
    return out


def clean(entries):
    """A list of {"id", "name"} from whatever was given: bad entries dropped, duplicates
    removed (first wins), order kept, at most MAX_WATCHED. Never raises."""
    out, seen = [], set()
    for entry in entries if isinstance(entries, (list, tuple)) else ():
        if isinstance(entry, str):
            entry = {"id": entry, "name": entry}
        if not isinstance(entry, dict):
            continue
        ident, name = entry.get("id"), entry.get("name")
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            continue
        seen.add(ident)
        name = name.strip() if isinstance(name, str) and name.strip() else ident
        out.append({"id": ident.strip(), "name": name[:80]})
        if len(out) >= MAX_WATCHED:
            break
    return out


def describe(watch_apps, limit=2):
    """"Only Chrome, VS Code +2" for the permission row, or None when every app is watched."""
    names = [e["name"] for e in clean(watch_apps)]
    if not names:
        return None
    shown = ", ".join(names[:limit])
    return f"Only {shown}" + (f" +{len(names) - limit}" if len(names) > limit else "")


def installed(dirs=None):
    """The apps a person has installed, for the picker: [{"id", "name", "path"}] sorted by
    name. Background-only apps and LMemM's own helper are left out. Reads each app's
    Info.plist; a damaged one is skipped. Needs no permission."""
    found, seen = [], set()
    for base in dirs if dirs is not None else APP_DIRS:
        base = os.path.expanduser(base)
        try:
            entries = sorted(os.scandir(base), key=lambda e: e.name.lower())
        except OSError:
            continue
        for entry in entries:
            if not entry.name.endswith(".app"):
                continue
            info = _plist(os.path.join(entry.path, "Contents", "Info.plist"))
            ident = info.get("CFBundleIdentifier")
            if not isinstance(ident, str) or not ident or ident in seen or ident in HIDDEN_IDS:
                continue
            if info.get("LSBackgroundOnly") or info.get("LSUIElement"):
                continue
            name = next((info[k] for k in ("CFBundleDisplayName", "CFBundleName")
                         if isinstance(info.get(k), str) and info[k].strip()), entry.name[:-4])
            seen.add(ident)
            found.append({"id": ident, "name": name.strip(), "path": entry.path})
    return sorted(found, key=lambda a: a["name"].lower())


def search(apps, query):
    """The apps whose name contains the query (case-insensitive); all of them for a blank query."""
    q = (query or "").strip().lower()
    return [a for a in apps if q in a["name"].lower()] if q else list(apps)


def _plist(path):
    try:
        with open(path, "rb") as fh:
            info = plistlib.load(fh)
        return info if isinstance(info, dict) else {}
    except (OSError, plistlib.InvalidFileException, ValueError, Exception):
        return {}
