"""LMemM - find what you saw or wrote before. Plain functions, no UI, no model.

Everything LMemM keeps about your work is split into small pieces, each with where it came from:

    screen   a line of text that was on a window (the thing's kept excerpts)
    wrote    a sentence you wrote there (the event trail, when writing capture is on)
    note     a note you left on a thing
    task     what a task was about: its goal, the last thing written, what was open
    title    a thing's window title

`search(question, pieces)` ranks them by how many of the question's rarer words they hold (a small tf-idf, with a
little extra for recent and for your own writing) and returns the best few, one per place. It is what "Ask your
memory" and "From earlier" are built on, and it never leaves this Mac: nothing here calls a model.
Secrets are dropped as the pieces are built (labels.redact); addresses and messages are kept, as in tasks.py.
"""

import math
import re
from datetime import datetime, timedelta

import labels
import notes
import tasks

STOP = set("""a an and are as at be but by can did do does for from had has have how i in is it its me my of on or our
so that the their them then there these they this to up was we were what when where which who why will with you your
about after again also any been before being into just more most not now only other over some such than too very
yesterday today tomorrow last week ago saw see seen wrote write written looked look find where what""".split())
MIN_WORDS = 1
PIECE_CHARS = 240
MAX_PIECES_PER_THING = 60


def words(text):
    return [w for w in re.findall(r"[a-z0-9][a-z0-9'’\-]{1,}", (text or "").lower()) if w not in STOP and len(w) >= 3]


def _stem(w):
    for tail in ("ing", "ed", "es", "s"):
        if w.endswith(tail) and len(w) - len(tail) >= 4:
            return w[: -len(tail)]
    return w


def stems(text):
    return [_stem(w) for w in words(text)]


def _when(iso):
    try:
        return datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


def _title(item):
    return tasks.clean(item.get("title") or item.get("doing") or "", 90)


def pieces(items, book=None, events=None, spans=None):
    """[{"text", "kind", "item", "app", "title", "at"}] for everything worth searching. `events`: trail write events;
    `spans`: tasks.entry_spans of the sessions they fall in, to say which thing each was written on."""
    out = []
    for iid, item in items.items():
        if tasks.off_limits(item):
            continue
        at = _when(item.get("last_seen"))
        base = {"item": iid, "app": item.get("app"), "title": _title(item), "at": at}
        lines = tasks.screen_lines(item)[-MAX_PIECES_PER_THING:]
        out += [{**base, "kind": "screen", "text": l[:PIECE_CHARS]} for l in lines]
        for n in item.get("notes", []):
            if n.get("text") and labels.redact([n["text"]]):
                out.append({**base, "kind": "note", "text": n["text"][:PIECE_CHARS]})
        if base["title"]:
            out.append({**base, "kind": "title", "text": base["title"]})
    for t in recent_task_rows(book):
        for key, label in (("goal", "Task goal"), ("last_wrote", "Last wrote"), ("open", "Open")):
            if t.get(key):
                first = next((i for i in t.get("items", []) if i in items), None)
                out.append({"kind": "task", "item": first, "app": "Task", "title": t["title"], "at": t["at"],
                            "text": f"{label}: {t[key]}"[:PIECE_CHARS]})
    out += written_pieces(events or [], items, spans or [])
    return out


def recent_task_rows(book):
    rows = []
    for run in (book or {}).values():
        at = _when(run.get("at"))
        for t in run.get("tasks") or []:
            rows.append({**t, "at": at})
    return rows


def written_pieces(events, items, spans):
    from trail_store import parse
    out = []
    for ev in events:
        if ev.get("kind") != "write":
            continue
        try:
            at = parse(ev["t"]).astimezone().replace(tzinfo=None)
        except (KeyError, ValueError):
            continue
        hit = next((iid for a, b, iid in spans if a - timedelta(seconds=6) <= at <= b + timedelta(seconds=6)), None)
        item = items.get(hit) if hit else None
        for piece in drop_drafts([breadcrumb_off(x) for x in ev.get("added") or []]):
            if labels.redact([piece]) and not tasks.own_text(piece) and len(piece.split()) >= 3:
                out.append({"kind": "wrote", "item": hit, "app": (item or {}).get("app") or ev.get("app"),
                            "title": _title(item) if item else "", "at": at, "text": piece[:PIECE_CHARS]})
    return out


def breadcrumb_off(text):
    """Reading a field sometimes brings the window's trail with it ('site · Page title > what you wrote'); keep what
    follows the last ' > '."""
    if " > " in text:
        text = text.rsplit(" > ", 1)[1]
    return text.strip()


def drop_drafts(pieces_):
    return tasks.drop_drafts(pieces_)


def all_spans(sessions_dir):
    """Time spans of every stored session: [(start, end, item id)], to place writing on the thing it was written on."""
    import json
    from pathlib import Path
    out = []
    for path in sorted(Path(sessions_dir).glob("*.json"))[-8:]:
        try:
            out += tasks.entry_spans(json.loads(path.read_text()))
        except (OSError, ValueError):
            continue
    return out


DAY_WORDS = (("yesterday", 1), ("today", 0))


def day_filter(question, now=None):
    """('yesterday' / 'today' in the question) -> the date to prefer, else None."""
    now = now or datetime.now()
    low = question.lower()
    for word, back in DAY_WORDS:
        if word in low:
            return (now - timedelta(days=back)).date()
    return None


def search(question, found, limit=6, now=None, exclude_item=None, min_hits=1):
    """The best pieces for a question: [{"piece", "score", "hits"}], at most one per (thing, kind) and `limit` in all."""
    now = now or datetime.now()
    q = list(dict.fromkeys(stems(question)))
    if len(q) < MIN_WORDS:
        return []
    docs = [(p, set(stems(p["text"]) + (stems(p["title"]) if p["kind"] != "title" else []))) for p in found
            if p.get("item") != exclude_item or exclude_item is None]
    df = {w: sum(1 for _p, s in docs if w in s) for w in q}
    total = max(len(docs), 1)
    day = day_filter(question, now)
    scored = []
    for p, s in docs:
        hit = [w for w in q if w in s]
        if len(hit) < min_hits:
            continue
        score = sum(math.log(1 + total / (1 + df[w])) for w in hit)
        score *= 1 + 0.15 * (len(hit) / len(q))
        if p["kind"] == "wrote":
            score *= 1.25
        if p["kind"] == "title":
            score *= 0.7
        at = p.get("at")
        if at:
            age = max((now - at).total_seconds() / 86400, 0)
            score *= 1 / (1 + 0.08 * age)
            if day and at.date() == day:
                score *= 1.5
        scored.append((score, p, hit))
    scored.sort(key=lambda x: -x[0])
    out, seen = [], set()
    for score, p, hit in scored:
        key = (p.get("item"), p["kind"])
        if key in seen or any(p["text"] == o["piece"]["text"] for o in out):
            continue
        seen.add(key)
        out.append({"piece": p, "score": round(score, 2), "hits": hit})
        if len(out) >= limit:
            break
    return out


def source_line(piece, now=None):
    now = now or datetime.now()
    at = piece.get("at")
    when = ""
    if at:
        days = (now.date() - at.date()).days
        when = "today" if days == 0 else "yesterday" if days == 1 else at.strftime("%-d %b")
    what = {"wrote": "you wrote", "note": "your note", "task": "task", "title": "window", "screen": "on screen"}[piece["kind"]]
    return " · ".join(x for x in (piece.get("app"), piece.get("title"), what, when) if x)


def gather(items, book=None, events=None, sessions_dir=None):
    """Every searchable piece, read from disk: the things, the task runs and (when writing capture is on) what you wrote."""
    import config
    events = tasks.trail_events() if events is None else events
    spans = all_spans(sessions_dir or config.paths().sessions_dir) if events else []
    return pieces(items, book, events, spans)


EARLIER_MIN_WORDS = 4
EARLIER_MIN_HITS = 2
EARLIER_FRESH_SECONDS = 600
EARLIER_KINDS = ("wrote", "screen", "note")
EARLIER_HIT_WORDS = 5
CODE_APPS = {"Code", "Visual Studio Code", "VS Code", "Terminal", "iTerm2", "Xcode", "Cursor", "PyCharm", "Sublime Text"}
FILE_TITLE = re.compile(r"\.(jsonl?|py|js|ts|tsx|md|txt|log|csv|yml|yaml|toml|html|css|sh|swift)\b", re.I)


def _worth_quoting(p):
    """A line worth showing as "from earlier": prose you wrote or read in a document, not a line of a log, code or terminal."""
    if p.get("app") in CODE_APPS or FILE_TITLE.search(p.get("title") or ""):
        return False
    text = (p.get("text") or "").strip()
    return len(text.split()) >= EARLIER_HIT_WORDS and (p["kind"] == "note" or tasks.prose(text))


def earlier(found, items, front_id, now=None):
    """What you wrote a moment ago on the thing in front, matched against everything else: the line you saw or wrote
    before that goes with it. -> {"text", "from", "item", "query"} or None. Needs two shared words, never the same thing."""
    now = now or datetime.now()
    mine = [p for p in found if p["kind"] == "wrote" and p.get("item") == front_id and p.get("at") and _worth_quoting(p)
            and 0 <= (now - p["at"]).total_seconds() <= EARLIER_FRESH_SECONDS and len(p["text"].split()) >= EARLIER_MIN_WORDS]
    if not mine or front_id not in items:
        return None
    query = max(mine, key=lambda p: p["at"])["text"]
    pool = [p for p in found if p["kind"] in EARLIER_KINDS and p.get("item") in items and p["text"] != query and _worth_quoting(p)]
    for hit in search(query, pool, limit=1, now=now, exclude_item=front_id, min_hits=EARLIER_MIN_HITS):
        p = hit["piece"]
        return {"text": p["text"], "from": source_line(p, now), "item": p["item"], "query": query}
    return None
