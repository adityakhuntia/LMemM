"""LMemM - Resume this project: where you left off, with the source of every line. Plain functions, no UI, no model.

Built only from what is already remembered, and nothing leaves this Mac. Every claim carries its kind and its source:

    authored   you wrote it (a note you left)                        "From your note"
    observed   LMemM saw it (a title, text on screen, a quote)       "Seen on screen in ..."
    inferred   a model's reading of a stretch of work (the task book) "AI inference"

A line with no source is never shown. Nothing here decides a goal, a decision, a blocker or "done" on its own:
  R20  Goal and stage come only from the task book, labelled AI inference. No task, no goal line.
  R21  A decision is only ever a quote of text that was on screen, labelled "seen, not confirmed". Several quotes
       from different things are shown side by side as "may not agree"; none is picked.
  R22  A blocker is only an open note of yours that asks something or says you are waiting or stuck.
  R23  The next step is your newest open note, else the task book's open step (AI inference), else none. Opening the
       latest thing is offered as an action, never written as a step.
  R24  Little history says so (state "limited"), old history says so (state "stale"), and neither is padded.
  R25  Things that tasks.off_limits() excludes never appear.
"""

import re
from datetime import datetime

import notes
import page_model
import projects
import store
import tasks

STALE_DAYS = 14
AWAY_HOURS = 4                     # away at least this long: the Resume button is the page's main action
MIN_CLAIMS = 2                     # fewer sourced claims than this and the brief says it has limited context
SEEN_SHOWN = 3
DECISIONS_SHOWN = 3
NOTES_SHOWN = 3
QUESTION = re.compile(r"\?|\b(blocked|waiting (?:on|for)|stuck|not sure|unsure|unclear)\b", re.I)

AUTHORED, OBSERVED, INFERRED = "authored", "observed", "inferred"
LABELS = {AUTHORED: "From your note", OBSERVED: "Seen on screen", INFERRED: "AI inference"}
PRIVACY = ("Built on this Mac from what LMemM already remembers. No model was asked and nothing was sent anywhere.")


def _when(iso):
    return page_model.parse(iso) if iso else None


def source(item, at=None, extra=None):
    at = at or item.get("last_seen")
    target = original_of(item)
    return {"item": item["id"], "title": page_model.title_of(item), "app": item.get("app", ""), "at": at,
            "can_open": target is not None, "open_label": "Open original" if target and target["kind"] == "url"
            else f"Open {item.get('app', '')}", **(extra or {})}


def claim(text, kind, item, now, at=None, label=None, **more):
    src = source(item, at)
    src["ago"] = page_model.ago(src["at"], now)
    return {"text": text, "kind": kind, "label": label or LABELS[kind], "source": src, **more}


def original_of(item):
    """What 'Open original' should open: a web address LMemM saw for this thing, else its app. None if neither."""
    for excerpt in reversed(item.get("content", {}).get("excerpts", [])):
        url = ((excerpt.get("source") or {}).get("url") or "").strip()
        if url:
            if not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.I):
                url = "https://" + url
            if url.lower().startswith(("http://", "https://")):
                return {"kind": "url", "value": url}
    return {"kind": "app", "value": item["app"]} if item.get("app") else None


def _task_for(book, member_ids):
    """The newest task whose things are mostly in this project, else None. Inference only; it never fills a gap."""
    best = None
    for run in (book or {}).values():
        at = _when(run.get("at"))
        for t in run.get("tasks") or []:
            ids = [i for i in t.get("items", [])]
            if ids and sum(i in member_ids for i in ids) * 2 > len(ids) and (at and (best is None or at > best[0])):
                best = (at, t)
    return best[1] if best else None


def said(ago):
    """"3 h ago" -> "3 h ago"; "Yesterday" -> "yesterday"; "Oct 3" -> "on Oct 3"."""
    return ago.lower() if ago.endswith("ago") or ago in ("Just now", "Yesterday") else f"on {ago}"


def _span(seconds):
    return store.duration(seconds)


def brief(reg, items, pid, now=None, book=None):
    now = now or datetime.now()
    name = reg["projects"][pid]["name"]
    mine = [i for i in projects.members(reg, items, pid, deep=True) if not tasks.off_limits(i)]
    out = {"pid": pid, "title": name, "state": "empty", "headline": "", "note": None, "ago": "", "away": False,
           "sections": [], "next": None, "latest": None, "used": {"things": len(mine), "notes": 0, "screen": 0, "tasks": 0},
           "privacy": PRIVACY}
    if not mine:
        out["note"] = "Nothing has been remembered in this project yet, so there is nothing to resume from."
        return out
    latest = mine[0]
    seen_at = _when(latest.get("last_seen"))
    days = (now - seen_at).days if seen_at else 0
    out["ago"] = page_model.ago(latest.get("last_seen"), now)
    out["away"] = bool(seen_at and (now - seen_at).total_seconds() >= AWAY_HOURS * 3600)
    out["latest"] = source(latest) | {"ago": out["ago"]}
    sections = []

    stand = [claim(f"Last worked in “{page_model.title_of(latest)}” ({latest.get('app', '')}), {said(out['ago'])}"
                   + (f", {_span(latest['seconds'])} there." if latest.get("seconds") else "."), OBSERVED, latest, now,
                   label="Observed")]
    sections.append({"id": "stand", "title": "Where things stand", "claims": stand})

    task = _task_for(book, {i["id"] for i in mine})
    if task:
        t_item = next((i for i in mine if i["id"] in task.get("items", [])), latest)
        goal = []
        if task.get("goal"):
            goal.append(claim(tasks.clean(task["goal"], 220), INFERRED, t_item, now,
                              extra_note=f"LMemM's reading of: {task['title']}" if task.get("title") else None))
        if goal:
            sections.insert(0, {"id": "goal", "title": "What you seem to be doing", "claims": goal})
        out["used"]["tasks"] = 1

    open_notes = []
    for item in mine:
        for n in notes.open_notes(item):
            open_notes.append((n["at"], n, item))
    open_notes.sort(key=lambda x: x[0], reverse=True)
    out["used"]["notes"] = len(open_notes)
    asks = [(a, n, i) for a, n, i in open_notes if QUESTION.search(n["text"])]
    steps = [(a, n, i) for a, n, i in open_notes if not QUESTION.search(n["text"])]

    if asks:
        a, n, i = asks[0]
        sections.append({"id": "blocker", "title": "Open question or blocker", "claims": [
            claim(n["text"], AUTHORED, i, now, at=a, label="From your note")]})
    nxt = None
    if steps:
        a, n, i = steps[0]
        nxt = claim(n["text"], AUTHORED, i, now, at=a, label="From your note")
    elif task and task.get("open"):
        t_item = next((i for i in mine if i["id"] in task.get("items", [])), latest)
        nxt = claim(tasks.clean(task["open"], 200), INFERRED, t_item, now)
    out["next"] = nxt

    rest = [(a, n, i) for a, n, i in open_notes if (a, n, i) not in asks[:1] and (not steps or (a, n, i) != steps[0])]
    if rest:
        sections.append({"id": "notes", "title": "Other open notes of yours", "detail": True,
                         "claims": [claim(n["text"], AUTHORED, i, now, at=a) for a, n, i in rest[:NOTES_SHOWN]]})

    quotes = []
    for item in mine:
        for ex in item.get("content", {}).get("excerpts", []):
            for q in ex.get("decision_quotes") or []:
                quotes.append((ex.get("last_seen") or item.get("last_seen"), q, item))
    seen_q, uniq = set(), []
    for at, q, item in sorted(quotes, key=lambda x: x[0] or "", reverse=True):
        key = re.sub(r"[^a-z0-9]", "", q.lower())
        if key not in seen_q:
            seen_q.add(key)
            uniq.append((at, q, item))
    if uniq:
        conflict = len({i["id"] for _a, _q, i in uniq[:DECISIONS_SHOWN]}) > 1
        sections.append({"id": "decisions", "title": "Possible decisions", "detail": True, "conflict": conflict,
                         "note": ("Seen in more than one place. These may not agree, and LMemM has not picked one."
                                  if conflict else "Text on screen that reads like a decision. Not confirmed by you."),
                         "claims": [claim(tasks.clean(q, 200), OBSERVED, i, now, at=a, label="Seen, not confirmed")
                                    for a, q, i in uniq[:DECISIONS_SHOWN]]})

    seen = []
    for item in mine[:4]:
        lines = tasks.screen_lines(item)[-1:]
        seen += [claim(tasks.clean(l, 200), OBSERVED, item, now, label="Seen on screen")
                 for l in lines]
    if seen:
        out["used"]["screen"] = len(seen)
        sections.append({"id": "seen", "title": "Last seen on screen", "detail": True, "claims": seen[:SEEN_SHOWN]})

    out["sections"] = sections
    sourced = sum(len(s["claims"]) for s in sections if s["id"] != "stand") + (1 if nxt else 0)
    if days >= STALE_DAYS:
        out["state"] = "stale"
        out["note"] = (f"Nothing new here for {page_model.plural(days // 7, 'week')}, so this may be out of date. "
                       "Check each source before relying on it.")
    elif sourced < MIN_CLAIMS:
        out["state"] = "limited"
        have = out["used"]["notes"]
        out["note"] = ("LMemM has limited context for this project: "
                       f"{page_model.plural(len(mine), 'thing')} remembered, "
                       + (f"{page_model.plural(have, 'note')} of yours" if have else "no notes of yours")
                       + " and little readable text. The most recent thing is the best place to start.")
        out["sections"] = [s for s in sections if s["id"] == "stand"]
    else:
        out["state"] = "rich"
    out["headline"] = (f"You were last here {said(out['ago'])}." if out["state"] != "empty" else "")
    return out


def as_text(b):
    """A short context brief to paste elsewhere. Every line says where it came from; inference is marked."""
    lines = [f"# Where I left off: {b['title']}", ""]
    if b.get("note"):
        lines += [f"_{b['note']}_", ""]
    for s in b["sections"]:
        lines.append(f"**{s['title']}**")
        if s.get("conflict"):
            lines.append(f"_{s['note']}_")
        for c in s["claims"]:
            lines.append(f"- {c['text']} ({c['label']}; {c['source']['title']}, {said(c['source']['ago'])})")
        lines.append("")
    if b.get("next"):
        c = b["next"]
        lines += ["**Next step**", f"- {c['text']} ({c['label']}; {c['source']['title']}, {said(c['source']['ago'])})", ""]
    return "\n".join(lines).strip()
