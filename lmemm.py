#!/usr/bin/env python3
"""
LMemM - the one command.

    lmemm.py [start] [--every N] [--input-events --input-app com.microsoft.VSCode]
                                      watch and remember (Ctrl-C to stop)
    lmemm.py memory [N] [--content] [--events]
                                      what's remembered + the latest session's timeline
    lmemm.py notes [--all] [PROJECT]  pending edits (your ⌃⌥N notes) by project
    lmemm.py notes done ID… | notes reopen ID…
    lmemm.py status | pause | resume  the running tracker
    lmemm.py pin                      force-save the current screen
    lmemm.py note                     open the note window (same as ⌃⌥N)
    lmemm.py delete-session ID (--dry-run | --confirm ID)

How it fits together: see ARCHITECTURE.md.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config
import notes
import store
import tracker

USAGE = ("usage: lmemm.py [start] [--every N] [--input-events --input-app APP] | memory [N] [--content] [--events]"
         " | notes [--all] [PROJECT] | notes done|reopen ID…"
         " | status | pause | resume | pin | note | delete-session ID (--dry-run | --confirm ID)")


# ---------------------------------------------------------------- memory

def show_memory(n, show_content=False, show_events=False):
    """What's remembered (one line per thing), then the latest session's timeline."""
    try:
        items = sorted(store.load_items().values(), key=lambda i: i["last_seen"], reverse=True)
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
            mark = "done" if notes.is_done(i, note_entry) else "open"
            print(f"{'':30}your note ({mark}, {notes.note_id(note_entry)}): \"{note_entry['text'][:80]}\"")
        if show_content:
            show_excerpts(i)
    sessions = sorted(Path(config.paths().sessions_dir).glob("*.json"))
    if sessions:
        doc = json.loads(sessions[-1].read_text())
        print(f"\nlatest session {doc['session']}\n")
        for e in doc["timeline"][-n:]:
            elapsed = e.get("for") or store.duration(e.get("seconds", 0))
            print(f"{e['from']}  {elapsed:>7}  {(e.get('mostly') or '-'):9}  {e['app'][:14]:14}  {e['doing']}")
    if show_events:
        show_input_events(n)
    print(f"\n{config.paths().items_file}")


def show_excerpts(item):
    excerpts = item.get("content", {}).get("excerpts", [])
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


def show_input_events(n):
    from input_store import prune_corpus
    root = Path(config.paths().memory_dir)
    if tracker.running_pid() is None:     # while running, the tracker owns pruning
        prune_corpus(root)
    for path in sorted((root / "inputs").glob("*.json"))[-1:]:
        doc = json.loads(path.read_text())
        cutoff = datetime.now(timezone.utc) - timedelta(hours=min(doc.get("retention_hours", 24), 24))
        events = [e for e in doc["events"] if datetime.fromisoformat(e["end_utc"]) >= cutoff]
        print(f"\ninput session {doc['session']}: {len(events)} events; {doc['status']}; "
              f"expired: {doc.get('expired', 0)}; capacity dropped: {doc.get('dropped_capacity', 0)}")
        navigation = [e for e in events if e["kind"] == "navigation_shortcut"]
        for action in ("tab_switch", "app_switch"):
            for direction in ("forward", "backward"):
                steps = sum(e["payload"]["count"] for e in navigation
                            if e["payload"]["action"] == action and e["payload"]["direction"] == direction)
                if steps:
                    print(f"  {action} {direction}: {steps} observed shortcut steps (not window distance)")
        for event in events[-n:]:
            print(f"  {event['start_utc']}  {event['kind'].replace('_', ' ')}: {event['payload']}")
            if event.get("observed_result"):
                print(f"    observed result: {event['observed_result']} — {event['observed_transition']}")
            if event.get("after_capture"):
                print(f"    after: {event['after_capture']}  item: {event.get('item', 'pending OCR')}")
            if event.get("before_capture"):
                print(f"    before: {event['before_capture']} ({event['before_age_seconds']}s old)")


# ---------------------------------------------------------------- commands

def cmd_start(args):
    from input_monitor import SUPPORTED_INPUT_APPS
    parser = argparse.ArgumentParser(prog="lmemm.py")
    parser.add_argument("--every", type=int, default=config.EVERY)
    parser.add_argument("--input-events", action="store_true")
    parser.add_argument("--input-app", action="append", default=[])
    parser.add_argument("--input-retention-hours", type=float, default=24)
    opts = parser.parse_args(args)
    if opts.every <= 0 or not 0 < opts.input_retention_hours <= 24:
        parser.error("positive capture interval and input retention of at most 24 hours required")
    if opts.input_events != bool(opts.input_app) or not set(opts.input_app) <= SUPPORTED_INPUT_APPS:
        parser.error("input monitoring requires --input-events --input-app com.microsoft.VSCode")
    tracker.Tracker(every=opts.every, input_apps=set(opts.input_app) or None,
                    input_retention_hours=opts.input_retention_hours).run()


def cmd_memory(args):
    counts = [a for a in args if a not in {"--content", "--events"}]
    try:
        if len(counts) > 1:
            raise ValueError
        count = int(counts[0]) if counts else 20
        if count < 1:
            raise ValueError
    except ValueError:
        sys.exit("usage: lmemm.py memory [N] [--content] [--events]")
    show_memory(count, show_content="--content" in args, show_events="--events" in args)


def cmd_notes(args):
    """The project view of pending edits, or mark some done / open again."""
    if args and args[0] in {"done", "reopen"}:
        ids = args[1:]
        if not ids:
            sys.exit("usage: lmemm.py notes done|reopen ID…")
        done = args[0] == "done"
        if tracker.send_control("notes_done", ids=ids, done=done):
            print(f"sent to the running tracker: {len(ids)} note(s) → {'done' if done else 'open'}")
            return
        items = store.load_items()
        found = notes.set_done(items, ids, done=done)
        missing = sorted(set(ids) - set(found))
        if found:
            record_offline_change(items)
            store.save_memory(items)
        print(f"{len(found)} note(s) marked {'done' if done else 'open'}"
              + (f"; not found: {', '.join(missing)}" if missing else ""))
        return
    include_done = "--all" in args
    wanted = " ".join(a for a in args if a != "--all").lower()
    view = notes.pending_view(store.load_items(), include_done=include_done)
    projects = [p for p in view["projects"] if wanted in p["project"].lower()]
    if not projects:
        print("no pending edits" + (f" in '{wanted}'" if wanted else "") + ". Press ⌃⌥N while LMemM runs to add one.")
        return
    total = sum(p["open"] for p in projects)
    print(f"{total} pending edit{'s' * (total != 1)}\n")
    for p in projects:
        print(f"{p['project']}  ({p['open']} open)")
        for entry in p["items"]:
            print(f"  {entry['app'][:14]:14}  {entry['what'][:70]}")
            for n in entry["notes"]:
                state = f"done {n['done']}" if "done" in n else n["at"]
                print(f"      {n['id']}  {'✓' if 'done' in n else '•'} {n['text'][:90]}   ({state})")
        print()
    print("mark one done:  lmemm.py notes done <id>")


def record_offline_change(items):
    """Changing memory while the tracker is stopped: keep session provenance consistent
    (otherwise later session deletion refuses, seeing an unexplained change)."""
    from input_store import InputStore
    memory_dir = Path(config.paths().memory_dir)
    if not (memory_dir / "contributions" / "baseline.json").exists():
        return
    before = store.load_items()
    evidence = InputStore("notes-" + datetime.now().strftime("%Y%m%d-%H%M%S"), memory_dir)
    evidence.initialize_baseline(before)
    evidence.checkpoint(items, [], [])
    evidence.close()


def cmd_control(action):
    pid = tracker.running_pid()
    if pid is None:
        sys.exit("tracker is not running")
    if action == "status":
        try:
            status = json.loads(Path(config.paths().status_file).read_text())
            if status["pid"] != pid:
                raise ValueError
            print(json.dumps(status, indent=2))
        except (OSError, ValueError, KeyError):
            sys.exit("running tracker has no current status")
    else:
        tracker.send_control(action)
        print(f"{action} requested; use status to check acknowledgement")


def cmd_delete_session(args):
    from input_store import delete_session, plan_session_deletion
    parser = argparse.ArgumentParser(prog="lmemm.py delete-session")
    parser.add_argument("session")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--confirm", metavar="SESSION")
    opts = parser.parse_args(args)
    if opts.confirm and opts.confirm != opts.session:
        parser.error("--confirm must match the session ID")
    p = config.paths()
    paths = {"data_dir": p.data_dir, "memory_dir": Path(p.memory_dir), "pidfile": p.pidfile}
    try:
        result = plan_session_deletion(opts.session, paths) if opts.dry_run else delete_session(opts.session, paths)
        print(json.dumps(result, indent=2))
    except ValueError as error:
        sys.exit(str(error))


def main():
    args = sys.argv[1:]
    cmd = args[0] if args and not args[0].startswith("-") else "start"
    rest = args[1:] if args and args[0] == cmd else args
    if cmd == "start":
        cmd_start(rest)
    elif cmd == "memory":
        cmd_memory(rest)
    elif cmd == "notes":
        cmd_notes(rest)
    elif cmd in {"status", "pause", "resume"}:
        cmd_control(cmd)
    elif cmd == "pin":
        tracker.pin()
    elif cmd == "note":
        tracker.note()
    elif cmd == "delete-session":
        cmd_delete_session(rest)
    else:
        sys.exit(USAGE)


if __name__ == "__main__":
    main()
