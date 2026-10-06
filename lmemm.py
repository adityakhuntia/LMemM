#!/usr/bin/env python3
"""
LMemM - one command for the whole pipeline.

    python3 lmemm.py                 start: capture on app/tab change, build a timeline of what you do
    python3 lmemm.py --every 10      same, with a 10s same-window timer (default 5s)
    python3 lmemm.py pin             pin the current screen in the running session
    python3 lmemm.py note            open the dictation note window (same as the ⌃⌥N hotkey)
    python3 lmemm.py memory [N]      what's remembered + the latest session's timeline
    python3 lmemm.py memory --content  also show retained excerpts and decision quotes
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

import argparse
import json
from pathlib import Path
import os
import sys

import tracker


def memory(n, show_content=False, show_events=False):
    """What's remembered (one line per thing), then the latest session's timeline."""
    import glob
    try:
        items = sorted(tracker.load_items().values(), key=lambda i: i["last_seen"], reverse=True)
        if not items and not show_events:
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
        for note_entry in i.get("notes", [])[-3:]:
            print(f"{'':30}your note: \"{note_entry['text'][:80]}\"")
        if show_content:
            excerpts = i.get("content", {}).get("excerpts", [])
            if not excerpts:
                print("  No content excerpt retained for this item.")
            for excerpt in excerpts[-3:]:
                source = excerpt["source"]
                origin = source.get("url") or source.get("window") or source.get("app") or "unknown"
                print(f"  Observed {excerpt['first_seen']} (last {excerpt['last_seen']}) — {origin}")
                text = excerpt["text"]
                print("    " + text[:600].replace("\n", "\n    ") + ("…" if len(text) > 600 else ""))
                for quote in excerpt.get("decision_quotes", []):
                    print(f"    Decision quote (unverified): {quote}")
    sessions = sorted(glob.glob(os.path.join(tracker.SESSIONS_DIR, "*.json")))
    if sessions:
        with open(sessions[-1]) as fh:
            doc = json.load(fh)
        print(f"\nlatest session {doc['session']}\n")
        for e in doc["timeline"][-n:]:
            elapsed = e.get('for') or tracker.duration(e.get('seconds', 0))
            print(f"{e['from']}  {elapsed:>7}  {(e.get('mostly') or '-'):9}  {e['app'][:14]:14}  {e['doing']}")
    if show_events:
        from datetime import datetime, timedelta, timezone
        root = Path(tracker.ITEMS_FILE).parent
        from input_store import prune_corpus
        # While running, the tracker owns pruning; inspection must not rewrite its active file.
        active = False
        try:
            pid = int(Path(tracker.PIDFILE).read_text().strip())
            if pid > 0:
                os.kill(pid, 0)
                active = True
        except (OSError, ValueError):
            pass
        if not active:
            prune_corpus(root)
        for path in sorted((root / "inputs").glob("*.json"))[-1:]:
            doc = json.loads(path.read_text())
            cutoff = datetime.now(timezone.utc) - timedelta(hours=min(doc.get("retention_hours", 24), 24))
            events = [e for e in doc["events"] if datetime.fromisoformat(e["end_utc"]) >= cutoff]
            print(f"\ninput session {doc['session']}: {len(events)} events; {doc['status']}; expired: {doc.get('expired', 0)}; capacity dropped: {doc.get('dropped_capacity', 0)}")
            navigation = [e for e in events if e["kind"] == "navigation_shortcut"]
            for action in ("tab_switch", "app_switch"):
                for direction in ("forward", "backward"):
                    steps = sum(e["payload"]["count"] for e in navigation if e["payload"]["action"] == action and e["payload"]["direction"] == direction)
                    if steps:
                        print(f"  {action} {direction}: {steps} observed shortcut steps (not window distance)")
            for event in events[-n:]:
                label = event["kind"].replace("_", " ")
                print(f"  {event['start_utc']}  {label}: {event['payload']}")
                if event.get("observed_result"):
                    print(f"    observed result: {event['observed_result']} — {event['observed_transition']}")
                if event.get("after_capture"):
                    print(f"    after: {event['after_capture']}  item: {event.get('item', 'pending OCR')}")
                if event.get("before_capture"):
                    print(f"    before: {event['before_capture']} ({event['before_age_seconds']}s old)")
    print(f"\n{tracker.ITEMS_FILE}")


def main():
    args = sys.argv[1:]
    cmd = args[0] if args and not args[0].startswith("--") else "start"

    if cmd in {"pause", "resume", "status"}:
        from input_store import private_write
        try:
            pid = int(Path(tracker.PIDFILE).read_text().strip())
            if pid <= 0:
                raise ValueError
            os.kill(pid, 0)
        except (OSError, ValueError):
            sys.exit("tracker is not running")
        if cmd == "status":
            try:
                status = json.loads(Path(tracker.PIDFILE).with_suffix(".status.json").read_text())
                if status["pid"] != pid:
                    raise ValueError
                print(json.dumps(status, indent=2))
            except (OSError, ValueError, KeyError):
                sys.exit("running tracker has no current status")
        else:
            private_write(Path(tracker.PIDFILE).with_suffix(".control.json"), {"pid": pid, "action": cmd})
            print(f"{cmd} requested; use status to check acknowledgement")
    elif cmd == "delete-session":
        from input_store import plan_session_deletion, delete_session
        parser = argparse.ArgumentParser(prog="lmemm.py delete-session")
        parser.add_argument("session")
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--dry-run", action="store_true")
        group.add_argument("--confirm", metavar="SESSION")
        opts = parser.parse_args(args[1:])
        if opts.confirm and opts.confirm != opts.session:
            parser.error("--confirm must match the session ID")
        paths = {"data_dir": tracker.DATA_DIR, "memory_dir": Path(tracker.ITEMS_FILE).parent, "pidfile": tracker.PIDFILE}
        try:
            result = plan_session_deletion(opts.session, paths) if opts.dry_run else delete_session(opts.session, paths)
            print(json.dumps(result, indent=2))
        except ValueError as error:
            sys.exit(str(error))
    elif cmd == "pin":
        tracker.pin()
    elif cmd == "note":
        tracker.note()
    elif cmd == "memory":
        counts = [a for a in args[1:] if a not in {"--content", "--events"}]
        try:
            if len(counts) > 1:
                raise ValueError
            count = int(counts[0]) if counts else 20
            if count < 1:
                raise ValueError
        except ValueError:
            sys.exit("usage: python3 lmemm.py memory [N] [--content]")
        memory(count, show_content="--content" in args, show_events="--events" in args)
    elif cmd == "peek":
        import peek
        rows = peek.load()
        if not rows:
            sys.exit("no frames yet. Run:  python3 lmemm.py")
        peek.summary(rows, listing="--list" in args)
    elif cmd == "start":
        from input_monitor import SUPPORTED_INPUT_APPS
        parser = argparse.ArgumentParser(prog="lmemm.py")
        parser.add_argument("--every", type=int, default=tracker.EVERY)
        parser.add_argument("--input-events", action="store_true")
        parser.add_argument("--input-app", action="append", default=[])
        parser.add_argument("--input-retention-hours", type=float, default=24)
        opts = parser.parse_args(args[1:] if args and args[0] == "start" else args)
        if opts.every <= 0 or not 0 < opts.input_retention_hours <= 24:
            parser.error("positive capture interval and input retention of at most 24 hours required")
        if opts.input_events != bool(opts.input_app) or not set(opts.input_app) <= SUPPORTED_INPUT_APPS:
            parser.error("input monitoring requires --input-events --input-app com.microsoft.VSCode")
        tracker.Tracker(every=opts.every, input_apps=set(opts.input_app) or None,
                        input_retention_hours=opts.input_retention_hours).run()
    else:
        sys.exit("usage: python3 lmemm.py [--every SECONDS] | pin | note | memory [N] | peek")


if __name__ == "__main__":
    main()
