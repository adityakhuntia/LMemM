"""LMemM - Resume this project: where you left off, with the source of every line. Plain functions, no UI, no model.

Built only from what is already remembered, and nothing leaves this Mac. Every claim carries its kind and its source:

    authored   you wrote it (a note you left)                        "From your note"
    observed   LMemM saw it (a title, text on screen, a quote)       "Seen on screen"
    inferred   a reading of a stretch of work (the task book, or an  "AI inference"
               AI chat that was still working)

A line with no source is never shown. Nothing here decides a goal, a decision, a blocker or "done" on its own:
  R20  Goal and stage come only from the task book, labelled AI inference. No task, no goal line.
  R21  A decision is only ever a quote of text that was on screen, labelled "seen, not confirmed". Several quotes
       from different things are shown side by side as "may not agree"; none is picked.
  R22  A blocker is only an open note of yours that asks something or says you are waiting or stuck.
  R23  The next step is chosen by relevance, not recency (R29), from your open notes on the work in front of you; else
       an AI chat that was still working (AI inference, "likely continuation"); else none, and the brief says so.
  R24  Little history says so (state "limited"), old history says so (state "stale"), and neither is padded.
  R25  Things that tasks.off_limits() excludes never appear.
  R29  Rank by (1) the requested scope, (2) being on the same work thread as the latest activity, (3) the note being
       on the thing in front of you, and only then (4) recency. Notes on other threads are listed apart.
  R30  Asked for a scope ("PR 25") with things not filed in a project, Resume does not pretend they are one project.
       It groups them into work threads on shared evidence (evidence.py R28), leads with the thread that names the
       scope, lists the rest apart, and says the project link is unconfirmed. If nothing names the scope, or two
       threads are close, it asks which one instead of guessing.
  R31  LMemM's own files and screens, and garbled text, are left out (evidence.py R26, R27). AI chat text is never
       quoted: its speaker is unknown and its text is noisy; the brief links to the chat instead.
"""

import os
import re
from datetime import datetime

import config
import evidence as ev
import notes
import page_model
import projects
import resume_feedback as rf
import source_ref
import store
import tasks

STALE_DAYS = 14
AWAY_HOURS = 4                     # away at least this long: the Resume button is the page's main action
MIN_CLAIMS = 2                     # fewer sourced claims than this and the brief says it has limited context
SEEN_SHOWN = 3
DECISIONS_SHOWN = 3
NOTES_SHOWN = 3
CLOSE = 0.6                        # two unscoped threads this close in score: ask which one
WORKING_WITHIN = 120               # seconds: a chat that showed 'running a command' this close to the end was mid-task
QUESTION = re.compile(r"\?|\b(blocked|waiting (?:on|for)|stuck|not sure|unsure|unclear)\b", re.I)

AUTHORED, OBSERVED, INFERRED = "authored", "observed", "inferred"
LABELS = {AUTHORED: "From your note", OBSERVED: "Seen on screen", INFERRED: "AI inference"}
CONFIDENCE = {AUTHORED: "your words", OBSERVED: "seen, not confirmed", INFERRED: "likely, not confirmed"}
PRIVACY = ("Built on this Mac from what LMemM already remembers. No model was asked and nothing was sent anywhere.")
BROWSERS = ("Safari", "Brave Browser", "Google Chrome", "Chrome", "Firefox", "Arc", "Microsoft Edge")
NO_NEXT = "I can identify the work, but I can't reliably tell what you planned to do next."


def _when(iso):
    return page_model.parse(iso) if iso else None


def label_of(item):
    """A trustworthy name for a thing: its title if it reads as words, else its app and kind (R27)."""
    title = ev.clean_title(item)
    if title:
        return title
    app = item.get("app") or "Unknown app"
    kind = item.get("kind")
    return f"{app} conversation" if kind == "ai_conversation" else f"{app} chat" if kind == "chat" else app


def original_of(item, exists=os.path.exists):
    """What 'Open' should open, most exact first (source_ref.py R36-R39): the saved page or file; else an address seen in the
    text LMemM kept; else only the app, with `problem` saying why there is no address (None: none was ever saved)."""
    saved = item.get("source")
    ok, problem = source_ref.check(saved, exists)
    if ok:
        return {"kind": saved["kind"], "value": saved["value"], "app": saved.get("app") or item.get("app"), "problem": None}
    for excerpt in reversed(item.get("content", {}).get("excerpts", [])):
        url = ((excerpt.get("source") or {}).get("url") or "").strip()
        if url and not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.I):
            url = "https://" + url
        url = source_ref.clean_url(url)
        if url:
            return {"kind": "url", "value": url, "app": (excerpt.get("source") or {}).get("app") or item.get("app"), "problem": None}
    return {"kind": "app", "value": item["app"], "app": item["app"], "problem": problem if isinstance(saved, dict) else None} if item.get("app") else None


def open_command(item, exists=os.path.exists):
    """-> {"args": [...], "exact": bool, "problem": str | None}: the macOS `open` call for this thing, or args None when
    there is nothing to open. A web address opens in the browser it was seen in, when that is a browser."""
    target = original_of(item, exists)
    if not target:
        return {"args": None, "exact": False, "problem": None}
    if target["kind"] == "url":
        browser = target.get("app") in config.BROWSERS
        return {"args": ["open", "-a", target["app"], target["value"]] if browser else ["open", target["value"]], "exact": True, "problem": None}
    if target["kind"] == "file":
        return {"args": ["open", target["value"]], "exact": True, "problem": None}
    return {"args": ["open", "-a", target["value"]], "exact": False, "problem": target.get("problem")}


def source(item, at=None, now=None):
    at = at or item.get("last_seen")
    target = original_of(item)
    when = _when(at)
    out = {"item": item["id"], "title": label_of(item), "app": item.get("app", ""), "at": at,
           "clock": when.strftime("%H:%M") if when else "", "can_open": target is not None,
           "exact": bool(target and target["kind"] in ("url", "file")), "problem": (target or {}).get("problem"),
           "open_label": "Open source" if target and target["kind"] in ("url", "file") else f"Open {item.get('app', '')}"}
    out["ago"] = page_model.ago(at, now) if now else ""
    return out


def claim(text, kind, item, now, at=None, label=None, **more):
    return {"text": text, "kind": kind, "label": label or LABELS[kind], "confidence": CONFIDENCE[kind],
            "source": source(item, at, now), **more}


def _task_for(book, member_ids):
    """The newest task whose things are mostly in this work, else None. Inference only; it never fills a gap."""
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


def _excluding(items, fb):
    """Things you told Resume not to use (R34): left out of the brief, still remembered."""
    keep = [i for i in items if i["id"] not in fb["exclude"]]
    return keep, [{"item": i["id"], "title": label_of(i)} for i in items if i["id"] in fb["exclude"]]


def _usable(items):
    """(things fit to use, [{"title", "why"}] left out). R25, R26."""
    keep, out = [], []
    for i in items:
        if tasks.off_limits(i):
            continue
        if ev.self_made(i):
            out.append({"item": i["id"], "title": i.get("title") or label_of(i), "why": "LMemM's own file or screen"})
        else:
            keep.append(i)
    return keep, out


def _rank_notes(open_notes, latest, thread_ids):
    """R29: notes on the work in front of you first (the latest thing, then its thread), recency only breaks ties."""
    def score(entry):
        at, _n, item = entry
        return (item["id"] in thread_ids, item["id"] == latest["id"], at)
    return sorted(open_notes, key=score, reverse=True)



def item_of_next(mine, c):
    return next((i for i in mine if i["id"] == c["source"]["item"]), mine[0])


def _next_from_messages(out, by_chat, item_of, scope, now, mine, thread_ids, sections, fb, authored):
    """R23/R32/R33: the request of yours that best fits the scope, and what became of it. Open before unknown; then the
    scope, the strength of the ask, and only then recency. A request that you said was done is not offered. What it
    offers is never "do X": it is "check where X got to", unless you chased it. Returns a claim or None."""
    best = None
    for chat, msgs in by_chat.items():
        mark = next((k for k in range(len(msgs) - 1, -1, -1) if ev.request_strength(msgs[k]["text"])), None)
        if mark is None:
            continue
        req = msgs[mark]
        item = item_of[req["item"]]
        sentence = ev.request_sentence(req["text"])
        if fb["steps"].get(rf.key(item["id"], sentence), {}).get("action") == "outdated":
            continue
        single = len({m["chat"] for m in authored if m["item"] == item["id"]}) <= 1
        status = ev.request_status(req, msgs, item, single)
        if status["status"] == "completed":
            continue
        strength = ev.request_strength(req["text"])
        hit = 1 if scope and ev.scope_hits({"title": "", "notes": [{"text": req["text"]}]}, scope) else 0
        rank = (status["status"] == "open", hit, strength, req["at"])
        if best is None or rank > best[0]:
            best = (rank, chat, req, msgs, item, sentence, status)
    if not best:
        return None
    _rank, chat, req, msgs, item, sentence, status = best
    line = [m for m in msgs if len(m["text"]) >= 12]
    timeline = [claim("“" + m["text"] + "”", AUTHORED, item, now, at=m["at"], label="You wrote this", chat=m["chat"]) for m in line]
    if status["signal"]:
        timeline.append(claim(f"{label_of(item)} was showing “running a command”.", OBSERVED, item, now, at=status["signal"], label="Seen on screen"))
    timeline.sort(key=lambda c: c["source"]["at"] or "")
    if len(timeline) > 1:
        sections.append({"id": "timeline", "title": "That chat, in order", "detail": True,
                         "note": "Only what you typed, and what the screen showed. Claude's own replies are not readable here.", "claims": timeline})
    if status["status"] == "open":
        step = f"You asked “{sentence}” and then wrote that it hadn't worked. Open that conversation and see where it stands."
        label = "AI inference · Unanswered request"
    else:
        step = (f"You asked Claude “{sentence}”. Claude's reply and the result aren't clear in what was remembered. "
                "Open that conversation to check where it got to.")
        label = "AI inference · Check the result"
    clock = ev.parse(req["at"]).strftime("%H:%M")
    quoted = re.sub(r"^(yup|yes|yeah|ok|okay|sure)[,.!\s]+", "", sentence, flags=re.I) or sentence
    base = f"You asked Claude: “{quoted}”."
    target = original_of(item)
    if target and target["kind"] in ("url", "file"):
        go = "Open the conversation to check."
    else:
        why_not = (target or {}).get("problem")
        go = (f"LMemM can't take you to that chat: {why_not}." if why_not else "LMemM didn't save an address for that chat, so it can't take you to it.")
    out["_lead"] = base + {
        "open": f" You then wrote that it hadn't worked. {go}",
        "likely_addressed": f" The screen showed Claude working afterwards, but I can't tell whether it finished. {go}",
    }.get(status["status"], f" I can't tell from this capture whether it finished. {go}")
    out["request"] = {"text": sentence, "status": status["status"], "label": status["label"], "why": status["why"],
                      "source": source(item, req["at"], now), "chat": chat}
    out["why"] = (f"Your latest request in that chat was at {clock} (“{sentence}”). Its status is {status['label'].lower()}: {status['why']}")
    out["confidence"] = ("Resume can point you to the conversation. It cannot tell what you should do there, because the reply and the result were not captured."
                         if status["status"] != "open" else "Your own follow-up says it hadn't worked; whether it is fixed now is not shown.")
    out["cant_tell"] = ["what Claude replied", "whether the work was finished or tested", "what you planned to do next"] if status["status"] != "open" \
        else ["whether it is fixed now"]
    chats = len({m["chat"] for m in authored if m["item"] == item["id"]})
    if status.get("ambiguous") or (chats > 1 and ev.last_signal(item)):
        out["cant_tell"].append(f"which chat the “running a command” screen belongs to ({label_of(item)} held {chats} chats; "
                                "your typed messages are matched to their chats from the event trail, the screen observation is not)")
    return claim(step, INFERRED, item, now, at=req["at"], label=label, key=rf.key(item["id"], sentence))


def _top(out, nxt, latest, here, replaced, items=None):
    """R35: the top of the brief is one honest sentence and one action. Everything else sits under 'Why this suggestion?'."""
    lead = out.pop("_lead", None)
    if not lead and nxt:
        text = nxt["text"] if len(nxt["text"]) <= 160 else nxt["text"][:157] + "…"
        lead = (f"Your open note says: “{text}”. Open where you wrote it to pick up from there." if nxt["kind"] == AUTHORED
                else f"LMemM's reading of this work suggests: {text} (an AI inference). Open it to check.")
    src = nxt["source"] if nxt else out["latest"]
    item = next((i for i in (items or []) if i["id"] == src["item"]), latest)
    target = original_of(item)
    chat = item.get("kind") == "ai_conversation"
    app = src.get("app") or "it"
    exact = bool(target and target["kind"] in ("url", "file"))
    problem = (target or {}).get("problem")
    thing = "chat" if chat else "file" if (item.get("source") or {}).get("kind") == "file" else "page"
    if exact:
        label, note = ("Open conversation" if chat else "Open source"), None
        primary, also = {"label": label, "mode": "source"}, None
    else:       # no address to reopen: lead with what LMemM saved, and offer the app only as what it is
        gone = f"{problem[0].upper()}{problem[1:]}." if problem else "LMemM didn't save an address for it."
        note = f"{gone} Open {app} starts the app only; it can't take you to the {thing}." if src["can_open"] else gone
        primary = {"label": "Show in LMemM", "mode": "lmemm"}
        also = {"label": f"Open {app}", "mode": "source"} if src["can_open"] else None
    cannot_open = "" if exact else f" It has no address for that {thing}, so it can open {app} but not take you to it."
    if not nxt:
        browser = app in BROWSERS
        reason = f", and {problem}" if problem else ", and LMemM has no saved address to reopen it"
        lead = f"I found “{here},” but I can't tell what you planned to do next{'. Open source to pick up from there.' if exact else reason + '.'}"
        many = len(items or []) > 1
        because = (f"“{here}” is {'the most recent' if many else 'the only recent'} source LMemM found. "
                   + ("It can reopen it, but nothing remembered shows what you planned to do next." if exact else
                      f"It has no address for it, so it can open {app} but not the exact {thing if (thing == 'file' or browser) else 'item'}, and nothing remembered shows what you planned to do next."))
    elif out.get("request"):
        because = (f"This is your latest request in {src['title']}, and nothing you wrote afterwards says it worked or didn't. "
                   "LMemM can't read Claude's replies, so it can't tell whether it finished." + cannot_open)
    elif replaced:
        because = "You replaced Resume's suggestion with your own words."
    elif nxt["kind"] == AUTHORED:
        because = ("It is your own open note on the work you were last in, so it ranks first. Whether it is still your plan isn't shown." + cannot_open)
    else:
        because = ("LMemM's reading of this work lists it as open. That is an inference, not something you wrote." + cannot_open)
    action = {"label": primary["label"], "mode": primary["mode"], "item": src["item"], "title": src["title"],
              "can_open": src["can_open"] or primary["mode"] == "lmemm", "note": note, "also": also and dict(also, item=src["item"])}
    return {"headline": lead, "because": because, "why_label": ("Why " + label[0].lower() + label[1:] + "?") if exact else f"Why can't Resume open the {thing}?",
            "action": action, "confirmed": bool(out.get("confirmed"))}


def _build(title, mine, now, book, extra=None, thread_items=None, authored=None, feedback=None):
    """The brief for one body of work (`mine`: its things, most recent first). `authored`: your typed messages."""
    scope_text = (extra or {}).get("scope")
    fb = feedback or rf.empty()
    out = {"title": title, "state": "empty", "headline": "", "note": None, "ago": "", "away": False, "sections": [],
           "next": None, "no_next": None, "why": None, "latest": None, "sources": [], "confidence": None,
           "used": {"things": len(mine), "notes": 0, "screen": 0, "tasks": 0}, "privacy": PRIVACY, **(extra or {})}
    if not mine:
        out["note"] = "Nothing has been remembered here yet, so there is nothing to resume from."
        return out
    latest = mine[0]
    seen_at = _when(latest.get("last_seen"))
    days = (now - seen_at).days if seen_at else 0
    out["ago"] = page_model.ago(latest.get("last_seen"), now)
    out["away"] = bool(seen_at and (now - seen_at).total_seconds() >= AWAY_HOURS * 3600)
    out["latest"] = source(latest, None, now)
    out["sources"] = [source(i, None, now) for i in mine[:6]]
    sections = []
    mine_ids = {i["id"] for i in mine}
    if thread_items is None:                              # a filed project: the thread of the latest activity ranks first
        grouped = ev.threads(mine)
        thread_ids = next(({m["id"] for m in g["items"]} for g in grouped if latest["id"] in {m["id"] for m in g["items"]}), {latest["id"]})
    else:
        thread_ids = {i["id"] for i in thread_items}

    here = label_of(latest)
    clock = out["latest"]["clock"]
    stand_text = (f"Most recent activity: {here}" + (f" at {clock}" if clock else "") + f" ({said(out['ago'])})"
                  + (f", {_span(latest['seconds'])} in total." if latest.get("seconds") else "."))
    stand_claims = [claim(stand_text, OBSERVED, latest, now, label="Observed")]
    for i in mine[:3]:
        signal = ev.last_signal(i) if i.get("kind") == "ai_conversation" else None
        if signal and ev.parse(i.get("last_seen")) and ev.parse(signal) and \
                (ev.parse(i["last_seen"]) - ev.parse(signal)).total_seconds() <= WORKING_WITHIN:
            n_chats = len({m["chat"] for m in (authored or []) if m["item"] == i["id"]})
            more = f" It held {n_chats} chats, so this can't be tied to one." if n_chats > 1 else ""
            stand_claims.append(claim(f"{label_of(i)} was showing “running a command” at {ev.parse(signal).strftime('%H:%M')}.{more}",
                                      OBSERVED, i, now, at=signal, label="Seen on screen"))
            break
    sections.append({"id": "stand", "title": "Where things stand", "claims": stand_claims})
    task = _task_for(book, mine_ids)
    if task:
        t_item = next((i for i in mine if i["id"] in task.get("items", [])), latest)
        if task.get("goal"):
            sections.insert(0, {"id": "goal", "title": "What you seem to be doing", "claims": [
                claim(tasks.clean(task["goal"], 220), INFERRED, t_item, now,
                      extra_note=f"LMemM's reading of: {task['title']}" if task.get("title") else None)]})
        out["used"]["tasks"] = 1

    open_notes = [(n["at"], n, item) for item in mine for n in notes.open_notes(item)]
    out["used"]["notes"] = len(open_notes)
    ranked = _rank_notes(open_notes, latest, thread_ids)
    on_thread = [e for e in ranked if e[2]["id"] in thread_ids]
    off_thread = [e for e in ranked if e[2]["id"] not in thread_ids]
    asks = [e for e in on_thread if QUESTION.search(e[1]["text"])]
    steps = [e for e in on_thread if not QUESTION.search(e[1]["text"])
             and fb["steps"].get(rf.key(e[2]["id"], e[1]["text"]), {}).get("action") != "outdated"]

    if asks:
        a, n, i = asks[0]
        sections.append({"id": "blocker", "title": "Open question or blocker", "claims": [
            claim(n["text"], AUTHORED, i, now, at=a)]})
    nxt = None
    if steps:
        a, n, i = steps[0]
        nxt = claim(n["text"], AUTHORED, i, now, at=a, key=rf.key(i["id"], n["text"]))
        out["why"] = ("Your open note on the work you were last in." if i["id"] == latest["id"]
                      else "Your open note on the same work thread as your latest activity.")
        out["confidence"] = "your words; whether it is still the plan is not shown"
    msgs = [m for m in (authored or []) if m["item"] in mine_ids]
    if msgs:
        by_chat = {}
        for m in msgs:
            by_chat.setdefault(m["chat"], []).append(m)
        recent = sorted(msgs, key=lambda m: m["at"], reverse=True)[:3]
        item_of = {i["id"]: i for i in mine}
        sections.insert(1, {"id": "asked", "title": "What you told Claude" if {i.get("app") for i in mine if i["id"] in {m["item"] for m in msgs}} == {"Claude"} else "What you wrote",
                            "claims": [claim("“" + m["text"] + "”", AUTHORED, item_of[m["item"]], now, at=m["at"],
                                             label="You wrote this", chat=m["chat"]) for m in recent]})
        out["used"]["typed"] = len(msgs)
        out["chats"] = len(by_chat)
        out["project_name"] = next((m["project"] for m in msgs if m["project"]), None)
        if not nxt:
            nxt = _next_from_messages(out, by_chat, item_of, scope_text, now, mine, thread_ids, sections, fb, msgs)
    if not nxt and task and task.get("open") and \
            fb["steps"].get(rf.key(next((i["id"] for i in mine if i["id"] in task.get("items", [])), latest["id"]), tasks.clean(task["open"], 200)), {}).get("action") != "outdated":
        t_item = next((i for i in mine if i["id"] in task.get("items", [])), latest)
        nxt = claim(tasks.clean(task["open"], 200), INFERRED, t_item, now, label="AI inference · Likely continuation",
                    key=rf.key(t_item["id"], tasks.clean(task["open"], 200)))
        out["why"] = "The task reading LMemM made of this work lists it as open."
        out["confidence"] = "likely continuation; not confirmed by you"
    replaced = False
    if nxt:                                                  # your corrections (R34)
        f = fb["steps"].get(nxt["key"], {})
        if f.get("action") == "replace":
            replaced = True
            out["_lead"] = f"Your next step, in your words: “{f['text']}”. Open where you were working to pick up from there."
            nxt = claim(f["text"], AUTHORED, item_of_next(mine, nxt), now, label="You wrote this", key=nxt["key"])
            out["why"] = "You replaced Resume's suggestion with your own words."
            out["confidence"] = "your words"
            out["request"] = out["cant_tell"] = None
        elif f.get("action") == "right":
            out["confirmed"] = True
            out["confidence"] = "you confirmed this suggestion"
    out["next"] = nxt
    out["cant_tell"] = out.get("cant_tell") if nxt else None
    if not nxt:
        out["no_next"] = NO_NEXT
    out["top"] = _top(out, nxt, latest, here, replaced, mine)

    rest = [e for e in (steps[1:] if steps else []) if e not in asks[:1]] + [e for e in asks[1:]]
    other_notes = rest + off_thread
    if other_notes:
        sections.append({"id": "notes", "title": "Other open notes in here", "detail": True,
                         "claims": [claim(n["text"], AUTHORED, i, now, at=a) for a, n, i in other_notes[:NOTES_SHOWN]]})

    quotes = []
    for item in mine:
        if item.get("kind") == "ai_conversation":
            continue                                        # R31: speaker unknown, text noisy
        for ex in item.get("content", {}).get("excerpts", []):
            for q in ex.get("decision_quotes") or []:
                if ev.clean_line(q, min_words=4, min_common=0.3):
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
        if item.get("kind") == "ai_conversation":
            continue
        lines = [l for l in tasks.screen_lines(item) if ev.clean_line(l)][-1:]
        seen += [claim(tasks.clean(l, 200), OBSERVED, item, now, label="Seen on screen") for l in lines]
    if seen:
        out["used"]["screen"] = len(seen)
        sections.append({"id": "seen", "title": "Last seen on screen", "detail": True, "claims": seen[:SEEN_SHOWN]})

    out["sections"] = sections
    sourced = sum(len(s["claims"]) for s in sections if s["id"] not in ("stand", "grouped")) + (1 if nxt else 0)
    if days >= STALE_DAYS:
        out["state"] = "stale"
        out["note"] = (f"Nothing new here for {page_model.plural(days // 7, 'week')}, so this may be out of date. "
                       "Check each source before relying on it.")
    elif sourced < MIN_CLAIMS and not (extra and extra.get("scope")):
        out["state"] = "limited"
        have = out["used"]["notes"]
        out["note"] = ("LMemM has limited context here: "
                       f"{page_model.plural(len(mine), 'thing')} remembered, "
                       + (f"{page_model.plural(have, 'note')} of yours" if have else "no notes of yours")
                       + " and little readable text.")
        out["sections"] = [s for s in sections if s["id"] == "stand"]
    else:
        out["state"] = "rich"
    out["headline"] = f"You were last here {said(out['ago'])}."
    return out


# ---------------------------------------------------------------- a project you filed

def brief(reg, items, pid, now=None, book=None, events=None, feedback=None):
    """Resume a project the user filed things in. Their filing is trusted: its things are one body of work, though
    notes on the thread of the latest activity rank before the rest (R29)."""
    now = now or datetime.now()
    name = reg["projects"][pid]["name"]
    mine, left = _usable(projects.members(reg, items, pid, deep=True))
    fb = feedback or rf.empty()
    mine, dropped = _excluding(mine, fb)
    authored = ev.authored_messages(events or [], {i["id"]: i for i in mine}, now) if events else []
    if mine and authored:
        latest = max(mine, key=lambda i: i.get("last_seen", ""))
        groups = ev.threads(mine)
        thread = next((g["items"] for g in groups if latest["id"] in {m["id"] for m in g["items"]}), [latest])
        thread_ids = {i["id"] for i in thread}
        authored = [m for m in authored if m.get("item") in thread_ids]
    else:
        thread = None
    out = _build(name, mine, now, book, extra=None, thread_items=thread, authored=authored, feedback=fb)
    out.update(pid=pid, scope=None, project_link="filed", left_out=left, others=[], candidates=[], excluded=dropped)
    if not mine:
        out["note"] = "Nothing has been remembered in this project yet, so there is nothing to resume from."
    return out


# ---------------------------------------------------------------- a scope, with things not filed anywhere

def _summary(group, now, scope=None):
    members = group["items"]
    open_notes = [(n["at"], n, i) for i in members for n in notes.open_notes(i)]
    open_notes.sort(key=lambda e: e[0], reverse=True)
    labels, seen = [], set()
    for i in members:
        w = label_of(i)
        if w not in seen:
            seen.add(w)
            labels.append(w)
    noted = next((i for i in members if notes.open_notes(i) and ev.clean_title(i)), None)
    clean = noted or next((i for i in members if ev.clean_title(i) and (i.get("seconds") or 0) >= ev.WEIGHTY_SECONDS), None)
    if scope:
        title = scope
    elif clean:
        title = ev.clean_title(clean) + (f" (+{len(members) - 1} related)" if len(members) > 1 else "")
    else:
        title = " and ".join(labels[:2]) if len(labels) > 1 else (labels[0] if labels else "Unnamed work")
    apps = sorted({i.get("app", "") for i in members if i.get("app")})
    last = members[0]
    return {"id": members[0]["id"], "title": title, "apps": apps, "last": last.get("last_seen"),
            "ago": page_model.ago(last.get("last_seen"), now), "things": len(members), "notes": len(open_notes),
            "note_texts": [n["text"] for _a, n, _i in open_notes[:3]],
            "sources": [source(i, None, now) for i in members[:4]], "item_ids": [i["id"] for i in members]}


def _score(group, scope, end):
    members = group["items"]
    hits = sum(min(ev.scope_hits(i, scope), 3) for i in members) if scope else 0
    sources = min(len(members), 4)
    authored = 1 if any(notes.open_notes(i) for i in members) else 0
    last = ev.parse(members[0].get("last_seen"))
    active = 1 if last and end and (end - last).total_seconds() <= 600 else 0
    recency = (1 - min((end - last).total_seconds(), 86400) / 86400) if last and end else 0
    return 10 * min(hits, 1) + 2 * sources + 3 * authored + 1.5 * active + recency, hits


def brief_scope(items, scope=None, now=None, book=None, pick=None, events=None, feedback=None):
    """Resume work that is not filed in a project. `scope`: what the user asked for ('PR 25'), or None. `pick`: the id
    of a thread the user chose from the candidates. R30."""
    now = now or datetime.now()
    mine, left = _usable(list(items.values()) if isinstance(items, dict) else list(items))
    fb = feedback or rf.empty()
    mine, dropped = _excluding(mine, fb)
    mine.sort(key=lambda i: i.get("last_seen", ""), reverse=True)
    groups = ev.threads(mine)
    stamps = [ev.parse(i.get("last_seen")) for i in mine if ev.parse(i.get("last_seen"))]
    end = max(stamps) if stamps else None
    rated = []
    for g in groups:
        score, hits = _score(g, scope, end)
        if any(n for i in g["items"] for n in notes.open_notes(i)) or any(i.get("kind") == "ai_conversation" for i in g["items"]) \
                or hits or len(g["items"]) > 1 or any((i.get("seconds") or 0) >= ev.WEIGHTY_SECONDS for i in g["items"]):
            rated.append((score, hits, g))
    rated.sort(key=lambda r: r[0], reverse=True)
    quiet = len(groups) - len(rated)
    base = {"scope": scope, "project_link": "unconfirmed", "left_out": left, "quiet": quiet, "pid": None, "excluded": dropped}
    if not rated:
        out = _build(scope or "Unfiled work", [], now, book, base)
        out.update(others=[], candidates=[])
        out["note"] = "Nothing here is substantial enough to resume from."
        return out
    chosen = None
    if pick:
        chosen = next((r for r in rated if r[2]["items"][0]["id"] == pick), None)
    elif scope:
        scoped = [r for r in rated if r[1] > 0]
        chosen = scoped[0] if scoped else None
        if not chosen:
            out = _build(scope, [], now, book, base)
            out.update(state="ambiguous", note=f"I couldn't find evidence of “{scope}” in these things. Which of these did you mean?",
                       others=[], candidates=[_summary(r[2], now) for r in rated[:4]])
            return out
    else:
        if len(rated) > 1 and rated[1][0] >= CLOSE * rated[0][0]:
            out = _build("Which work?", [], now, book, base)
            out.update(state="ambiguous", note="This holds more than one piece of work and none is clearly the one you were on. "
                                              "Which do you want to resume?",
                       others=[], candidates=[_summary(r[2], now) for r in rated[:4]])
            return out
        chosen = rated[0]
    score, hits, group = chosen
    summ = _summary(group, now, scope)
    typed = ev.authored_messages(events, items if isinstance(items, dict) else {i["id"]: i for i in items}, now) if events else None
    extra = dict(base, matched=[
        {"item": i["id"], "title": label_of(i), "hits": ev.scope_hits(i, scope)} for i in group["items"] if scope and ev.scope_hits(i, scope)])
    out = _build(summ["title"], group["items"], now, book, extra, thread_items=group["items"], authored=typed, feedback=fb)
    out["maybe"] = [{"item": i["id"], "title": label_of(i), "note": f"{label_of(i)} covers similar ground, but I can't tell whether it is part of this work."}
                    for i in group["maybe"]]
    if out.get("chats"):
        out["relation"] = (f"You typed in {page_model.plural(out['chats'], 'Claude chat')}" + (f" in your “{out['project_name']}” project" if out.get("project_name") else "")
                           + ", all within this session.")
    if scope and out["state"] != "empty":
        out["headline"] = f"Matched “{scope}” in {page_model.plural(len(extra['matched']), 'place')}. " + out["headline"]
    rest = [_summary(r[2], now) for r in rated if r[2] is not group]
    out.update(candidates=[], others=[o for o in rest if o["notes"]][:4], quiet=quiet + len([o for o in rest if not o["notes"]]))
    out["summary"] = summ
    out["covers"] = ", ".join(dict.fromkeys(label_of(i) for i in group["items"]))
    return out


def why_groups(b):
    """R35: the evidence behind the top line, in four kinds that are never mixed:
    what you wrote, what the app observed, what Resume inferred, what Resume cannot determine."""
    by = {s["id"]: s for s in b["sections"]}
    wrote, seen = [], []
    lead = (b.get("request") or {}).get("chat")
    for sid in ("timeline", "asked"):
        for c in (by.get(sid) or {}).get("claims", []):
            if c["text"] not in {w["text"] for w in wrote}:
                wrote.append(dict(c, text=c["text"] + " (in your other chat)") if lead and c.get("chat") not in (None, lead) else c)
    wrote = sorted(wrote, key=lambda c: c["source"]["at"] or "")[-6:]
    for sid in ("stand", "seen"):
        seen += (by.get(sid) or {}).get("claims", [])
    for c in (by.get("timeline") or {}).get("claims", []):
        if c["kind"] == OBSERVED and c["text"] not in {x["text"] for x in seen}:
            seen.append(c)
    nxt = b.get("next")
    if nxt and nxt["kind"] == AUTHORED and nxt["text"] not in {w["text"] for w in wrote}:
        wrote.insert(0, nxt)
    inferred = ([nxt] if nxt and nxt["kind"] != AUTHORED else []) + (by.get("goal") or {}).get("claims", [])
    lines = []
    if b.get("request"):
        lines.append(f"Status of your request: {b['request']['label']}. {b['request']['why']}")
    if b.get("confidence"):
        lines.append("Confidence: " + b["confidence"])
    cannot = list(b.get("cant_tell") or [])
    shown = {"timeline", "asked", "stand", "seen", "goal"}
    more = [s for s in b["sections"] if s["id"] not in shown]
    return [("What you wrote", wrote), ("What the app observed", seen), ("What Resume inferred", inferred)], lines, cannot, more


def as_text(b):
    """A short context brief to paste elsewhere: one line and one action first, then why. Every line says where it came
    from; inference is marked."""
    lines = [f"# Where I left off: {b['title']}", ""]
    top = b.get("top")
    if top:
        act = top["action"]
        lines += [f"**{top['headline']}**", f"Action: {act['label']} ({act['title']})"
                  + (f". {act['note']}" if act.get("note") else "")
                  + (f" Also: {act['also']['label']}." if act.get("also") else ""), ""]
    if b.get("project_link") == "unconfirmed":
        lines += ["_These things aren't filed in a project, so Resume kept together only what clearly belongs together._"]
        if b.get("relation"):
            lines += [f"_{b['relation']}_"]
        elif b.get("covers"):
            lines += [f"_This work: {b['covers']}._"]
        if b.get("matched"):
            lines += ["_Matched “%s” in: %s._" % (b["scope"], ", ".join(m["title"] for m in b["matched"]))]
        lines += [""]
    if b.get("note"):
        lines += [f"_{b['note']}_", ""]
    if b.get("sections"):
        groups, why, cannot, more = why_groups(b)
        lines.append(f"## {top['why_label'] if top else 'Why this suggestion?'}")
        if top:
            lines.append(top["because"])
        for title, claims in groups:
            if claims:
                lines.append(f"**{title}**")
                lines += [f"- {c['text']} ({c['label']}; {c['source']['title']}, {said(c['source']['ago'])})" for c in claims]
        lines += [f"- {w}" for w in why]
        if cannot:
            lines.append("**What Resume cannot determine**")
            lines += [f"- {c}" for c in cannot]
        lines.append("")
        for s in more:
            lines.append(f"**{s['title']}**")
            if s.get("conflict"):
                lines.append(f"_{s['note']}_")
            for c in s["claims"]:
                lines.append(f"- {c['text']} ({c['label']}; {c['source']['title']}, {said(c['source']['ago'])})")
            lines.append("")
    for o in b.get("others") or []:
        lines.append(f"Other open work: {o['title']} ({page_model.plural(o['notes'], 'open note')}, last {said(o['ago'])})")
    for m in b.get("maybe") or []:
        lines.append(f"Possibly related (uncertain): {m['note']}")
    left = b.get("left_out") or []
    if left:
        lines.append(f"Left out: {page_model.plural(len(left), 'thing')} that is LMemM's own file or screen ({', '.join(l['title'] for l in left[:3])}).")
    if b.get("excluded"):
        lines.append(f"Left out because you said not to use {page_model.plural(len(b['excluded']), 'source')}: {', '.join(e['title'] for e in b['excluded'][:3])}.")
    if b.get("quiet"):
        lines.append(f"Not enough to describe: {page_model.plural(b['quiet'], 'other thing')} with nothing open.")
    return "\n".join(lines).strip()
