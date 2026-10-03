#!/usr/bin/env python3
"""
LMemM - look at what the logger collected.

    python3 peek.py            # summary of everything in ./data
    python3 peek.py --list     # one line per frame

This is the step-1 payoff: it tells you how your screen time actually
breaks down, how boring the average frame is, and how much disk this costs.
"""

import glob
import json
import os
import sys
from collections import Counter

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def load(since=None):
    rows = []
    for p in sorted(glob.glob(os.path.join(DATA_DIR, "*.json"))):
        if since and os.path.basename(p)[:-5] < since:
            continue
        try:
            with open(p) as f:
                rows.append(json.load(f))
        except Exception:
            pass
    return rows


def main():
    rows = load()
    if not rows:
        sys.exit(f"No frames yet in {DATA_DIR}. Run:  python3 lmemm.py")
    summary(rows, listing="--list" in sys.argv)


def summary(rows, listing=False):
    if not rows:
        print("no frames.")
        return
    if listing:
        for r in rows:
            label = r.get("tab_title") or r.get("window") or "-"
            print(f"{r['ts']}  {str(r.get('app') or '?'):20.20}  {label:.70}")
        print()

    total_mb = sum(r.get("bytes", 0) for r in rows) / 1e6
    apps = Counter(r.get("app") or "?" for r in rows)

    # how often does the app change between consecutive frames?
    switches = sum(
        1 for a, b in zip(rows, rows[1:]) if a.get("app") != b.get("app")
    )

    # how often is the window title identical to the previous frame?
    # a rough proxy for "nothing happened"
    same = sum(
        1 for a, b in zip(rows, rows[1:])
        if (a.get("window"), a.get("url")) == (b.get("window"), b.get("url"))
    )

    print(f"frames            {len(rows)}")
    print(f"span              {rows[0]['ts']}  ->  {rows[-1]['ts']}")
    print(f"disk              {total_mb:.1f} MB  ({total_mb / max(len(rows),1):.2f} MB/frame)")
    print(f"app switches      {switches}/{len(rows)-1}  ({100*switches/max(len(rows)-1,1):.0f}%)")
    print(f"unchanged context {same}/{len(rows)-1}  ({100*same/max(len(rows)-1,1):.0f}%)"
          "   <- candidates the near-duplicate gate would skip")
    print(f"\ntop apps")
    for app, c in apps.most_common(12):
        bar = "#" * int(30 * c / apps.most_common(1)[0][1])
        print(f"  {app:24.24} {c:4d}  {bar}")

    missing = [r["ts"] for r in rows if not r.get("window")]
    if missing:
        print(f"\nframes with no window title: {len(missing)}"
              "  <- if this is high, check Accessibility permission")


if __name__ == "__main__":
    main()
