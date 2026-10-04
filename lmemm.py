#!/usr/bin/env python3
"""
LMemM - one command for the whole pipeline.

    python3 lmemm.py                 start: capture on app/tab change, build a timeline of what you do
    python3 lmemm.py --every 10      same, with a 10s same-window timer (default 5s)
    python3 lmemm.py pin             pin the current screen in the running session
    python3 lmemm.py note            open the dictation note window (same as the ⌃⌥N hotkey)
    python3 lmemm.py memory [N]      what's remembered + the latest session's timeline
    python3 lmemm.py peek [--list]   text summary of every frame kept on disk

How it fits together:
    tracker.py     watches macOS for app / tab / window changes, takes the screenshot
    resolver.py    OCR + layout -> typed on-screen objects
    understand.py  objects -> what you're doing (app, action, target, details), by rules
    -> data/memory/memory.json             one entry per thing (draft, doc, chat, file, page),
                                           updated in place when you come back to it
       data/memory/sessions/<session>.json when you were on which thing

Background version: ./run.sh start / ./run.sh stop.
"""

import json
import os
import sys

import tracker


def memory(n):
    """What's remembered (one line per thing), then the latest session's timeline."""
    import glob
    try:
        items = sorted(tracker.load_items().values(), key=lambda i: i["last_seen"], reverse=True)
        if not items:
            raise ValueError
    except (OSError, ValueError):
        sys.exit("nothing remembered yet. Run:  python3 lmemm.py")
    print("remembered (most recent first)\n")
    for i in items[:n]:
        print(f"{i['last_seen'][11:19]}  {i['seconds']:5d}s  x{i['visits']:<2}  "
              f"{(i.get('mostly') or '-'):9}  {i['app'][:14]:14}  {i['doing']}")
        acts = i.get("activity", {})
        split = "  ".join(f"{c} {a['seconds']}s" for c, a in acts.items() if a["seconds"])
        if split:
            print(f"{'':30}{split}")
        typed = acts.get("typing", {}).get("text")
        if typed:
            print(f"{'':30}typed: {typed[-1][:80]}")
        for n in i.get("notes", [])[-3:]:
            print(f"{'':30}your note: \"{n['text'][:80]}\"")
    sessions = sorted(glob.glob(os.path.join(tracker.SESSIONS_DIR, "*.json")))
    if sessions:
        doc = json.load(open(sessions[-1]))
        print(f"\nlatest session {doc['session']}\n")
        for e in doc["timeline"][-n:]:
            print(f"{e['from']}  {e['for']:>7}  {(e.get('mostly') or '-'):9}  {e['app'][:14]:14}  {e['doing']}")
    print(f"\n{tracker.ITEMS_FILE}")


def main():
    args = sys.argv[1:]
    cmd = args[0] if args and not args[0].startswith("--") else "start"

    if cmd == "pin":
        tracker.pin()
    elif cmd == "note":
        tracker.note()
    elif cmd == "memory":
        memory(int(args[1]) if len(args) > 1 else 20)
    elif cmd == "peek":
        import peek
        rows = peek.load()
        if not rows:
            sys.exit("no frames yet. Run:  python3 lmemm.py")
        peek.summary(rows, listing="--list" in args)
    elif cmd == "start":
        every = tracker.EVERY
        if "--every" in args:
            try:
                every = int(args[args.index("--every") + 1])
            except (IndexError, ValueError):
                sys.exit("usage: python3 lmemm.py [--every SECONDS] | pin | note | memory [N] | peek")
        tracker.Tracker(every=every).run()
    else:
        sys.exit("usage: python3 lmemm.py [--every SECONDS] | pin | note | memory [N] | peek")


if __name__ == "__main__":
    main()
