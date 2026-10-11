"""LMemM - the recap: what you did, ready to paste into a standup or a status update. No model, nothing sent.

From the stored task runs: for each task, the time on it, its stage, the goal, the last thing you wrote and what is
still open. Tasks that came back under the same title across runs are merged.
"""

from datetime import datetime, timedelta

import memory_search
import store


def merged(book, since):
    """{title: {...}} from every run at or after `since`, longest time first."""
    out = {}
    for run in (book or {}).values():
        at = memory_search._when(run.get("at"))
        if not at or at < since:
            continue
        for t in run.get("tasks") or []:
            row = out.setdefault(t["title"], {"title": t["title"], "seconds": 0, "stage": t.get("stage"), "goal": t.get("goal"),
                                              "open": None, "last_wrote": None, "at": at})
            row["seconds"] += t.get("seconds", 0)
            if at >= row["at"]:
                row.update(stage=t.get("stage") or row["stage"], goal=t.get("goal") or row["goal"], at=at)
                row["open"] = t.get("open") or row["open"]
                row["last_wrote"] = t.get("last_wrote") or row["last_wrote"]
    return sorted(out.values(), key=lambda r: -r["seconds"])


def build(book, days=1, now=None):
    """The recap text for the last `days` day(s) (1 = since midnight today)."""
    now = now or datetime.now()
    since = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    rows = merged(book, since)
    if not rows:
        return ""
    total = sum(r["seconds"] for r in rows)
    head = "today" if days == 1 else f"the last {days} days"
    lines = [f"# What I worked on {head} ({store.duration(total)} across {len(rows)} task{'s' * (len(rows) != 1)})", ""]
    for r in rows:
        lines.append(f"- **{r['title']}** ({r['stage'] or 'other'}, {store.duration(r['seconds'])})")
        if r["goal"]:
            lines.append(f"  - {r['goal']}")
        if r["last_wrote"]:
            lines.append(f"  - Last wrote: {r['last_wrote']}")
    left = [r for r in rows if r["open"]]
    if left:
        lines += ["", "**Still open**"] + [f"- {r['title']}: {r['open']}" for r in left]
    return "\n".join(lines)
