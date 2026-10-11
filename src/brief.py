"""LMemM - the context brief: what to paste into Claude or ChatGPT so it already knows what you are doing.

Built from what is stored, with no model call and nothing sent anywhere: the task you are on (or the latest one),
its goal and stage, what you wrote recently, the open step, the windows involved with a few lines of what was on
them, and your open notes. Plain markdown, capped (BRIEF_CHARS) so it stays cheap to paste. `recap.py` does the same
for "what did I do".
"""

from datetime import datetime

import memory_search
import notes
import tasks

BRIEF_CHARS = 3200
WROTE_PIECES = 6
SCREEN_LINES = 5


def pick_task(book, items, front_id=None, now=None):
    """(task, run time) for the thing in front, else the most recent task; (None, None) when there is none."""
    now = now or datetime.now()
    rows = sorted(((r["at"], r) for r in memory_search.recent_task_rows(book) if r.get("at")), key=lambda x: x[0], reverse=True)
    mine = [(at, t) for at, t in ((r["at"], r) for _a, r in rows) if front_id and front_id in t.get("items", [])]
    for at, t in (mine or [(r["at"], r) for _a, r in rows])[:1]:
        return t, at
    return None, None


def build(items, book, front_id=None, found=None, now=None):
    """The brief as text. `found`: memory_search.pieces(...) (for what you wrote); None -> only what is in the items."""
    now = now or datetime.now()
    task, at = pick_task(book, items, front_id, now)
    ids = [i for i in (task or {}).get("items", []) if i in items] or ([front_id] if front_id in items else [])
    if not ids:
        return ""
    lines = [f"# Context from my Mac ({now.strftime('%-d %b %H:%M')})", ""]
    if task:
        lines.append(f"**What I'm doing:** {task['title']}" + (f" ({task['stage']})" if task.get("stage") else ""))
        if task.get("goal"):
            lines.append(f"**Goal:** {task['goal']}")
        if task.get("open"):
            lines.append(f"**Open:** {task['open']}")
        lines.append("")
    else:
        lines += [f"**I'm working on:** {tasks.clean(items[ids[0]].get('title') or items[ids[0]].get('doing'), 90)}", ""]
    wrote = [p for p in (found or []) if p["kind"] == "wrote" and p.get("item") in ids][-WROTE_PIECES:]
    if wrote:
        lines.append("**What I wrote recently:**")
        lines += [f"- {p['text']}" for p in wrote]
        lines.append("")
    lines.append("**Windows involved:**")
    for iid in ids[:8]:
        it = items[iid]
        lines.append(f"- {it.get('app')}: {tasks.clean(it.get('title') or it.get('doing'), 90)}")
    shown = False
    for iid in ids[:5]:
        text = tasks.screen_lines(items[iid])[-SCREEN_LINES:]
        if text:
            if not shown:
                lines += ["", "**Text from those windows:**"]
                shown = True
            lines.append(f"_{items[iid].get('app')} · {tasks.clean(items[iid].get('title') or '', 60)}_")
            lines += [f"> {l[:200]}" for l in text]
    open_notes = [(items[i].get("title") or "", n) for i in ids for n in notes.open_notes(items[i])]
    if open_notes:
        lines += ["", "**My open notes:**"] + [f"- {n['text']}" for _t, n in open_notes[:5]]
    text = "\n".join(lines).strip()
    return text if len(text) <= BRIEF_CHARS else text[:BRIEF_CHARS].rsplit("\n", 1)[0] + "\n…"
