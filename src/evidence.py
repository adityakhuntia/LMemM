"""LMemM - is this text fit to be evidence? And which things belong to the same piece of work? No UI, no model.

Resume (resume.py) must not turn noise into a story. Three jobs, all plain functions:

  self_made(item)       LMemM's own files and screens (its logs, memory, status) are never the user's work.
  clean_title / clean_line
                        OCR that is garbled is kept for inspection but never promoted into a brief.
  threads(items)        groups things only on evidence they share (a distinctive word, a number like 180DC), so
                        unrelated work in one session stays separate. Browser tab strips and menus do not link.

  R26  LMemM's own files, logs, status lines and pill text are not work evidence (self_made, own_line).
  R27  A title or line is quoted only if its words are well formed and mostly ordinary words. Otherwise the brief
       names the source by app and kind ("Claude conversation") and leaves the text to the source page.
  R28  Two things join one work thread only through a strong shared token (such as 180dc), never through time,
       app switching, or a shared window. Sharing a few ordinary words only makes them "maybe related": they are kept
       apart and the brief says the link is uncertain. The shared words themselves are never shown to the user.
  R32  What you typed (the event trail's write events) is the best evidence of the task: it is certainly yours. It is
       assembled into messages per chat, quoted verbatim, and ranks above anything read from the screen.
"""

import difflib
import re
from datetime import datetime

import tasks

# files LMemM itself writes: opening one in an editor is LMemM observing itself, not the user's project
OWN_FILES = {"labels_log.jsonl", "labels.json", "labels_usage.json", "memory.json", "tasks.json", "projects.json",
             "nextsteps.json", "onboarding.json", "lmemm.log", ".lmemm.status.json", "run.json"}
OWN_PATH = re.compile(r"data\s*[>/]\s*(?:memory|trail|runs)\b", re.I)
OWN_LINE = re.compile(r"pending\s+\S?dit\b|\bLMemM\b.{0,12}\b(?:card|pill)\b|labels_log|\"open\"\s*:", re.I)

COMMON = frozenset("""a about above after again all also am an and any are as at be because been before being between both
but by can could did do does doing down during each few for from further had has have having he her here him his how i
if in into is it its just let lets like make me more most my no nor not now of off on once only or other our out over own
same she should so some such than that the their them then there these they this those through to too under until up
us very was we were what when where which while who why will with would you your yours yes okay thanks please
build feature thread open read check line lines note notes page tasks task project item items first next last new old
good better right wrong back work working worked use used using see seen show shows make made take took get got put set
look looks feel feels want need needs run runs ran test tests code file files time times day days one two three four
five many much well still even every while without within""".split())

ANCHOR_STOP = COMMON | frozenset("""claude chatgpt gpt thread threads https http google chrome safari window windows file edit view insert
format tools help drafts inbox sent unread slide slides deck remind reminder remember memory screen text title untitled
document documents folder tab tabs chat chats message messages email emails mail python python3 code command""".split())

SHAPE_WORD = re.compile(r"^(?:[A-Za-z]+(?:['’\-][A-Za-z]+)*|\$?\d[\d,.:%]*|\d+[A-Za-z]{1,3}\d*|[A-Za-z]{1,3}\d{1,3})$")
SHAPE_KNOWN = {"LMemM", "ChatGPT", "VS", "PR"}
STRONG = re.compile(r"^\d+[a-z]+\d*$")

WEIGHTY_SECONDS = 8            # a thing glanced at for less than this, with no note, never joins a thread on weak words
WEAK_LINK_TERMS = 3
MAX_DF = 4                     # a word seen in more things than this is chrome, not a topic


def tokens(text):
    return re.findall(r"[^\s]+", text or "")


def _stripped(tok):
    return tok.strip(".,;:!?()[]{}\"“”‘’")


def well_formed(tok):
    t = _stripped(tok)
    if not t:
        return True
    if t in SHAPE_KNOWN or SHAPE_WORD.match(t):
        return not (re.search(r"[a-z][A-Z]", t) and t not in SHAPE_KNOWN)
    return False


def common_share(words):
    words = [w.lower() for w in words if re.search(r"[A-Za-z]", w)]
    return sum(w in COMMON for w in words) / len(words) if words else 0.0


def clean_title(item):
    """The thing's title if it reads as words, else None (the caller names it by app and kind)."""
    title = (item.get("title") or "").strip()
    toks = [t for t in tokens(title) if _stripped(t) and _stripped(t) not in "-|·"]
    if not toks or not all(well_formed(t) for t in toks):
        return None
    return title


def clean_line(line, min_words=4, min_common=0.5):
    """A line of seen text worth quoting: well formed, long enough, and mostly ordinary words (R27)."""
    toks = [t for t in tokens(line) if _stripped(t)]
    if len(toks) < min_words or not all(well_formed(t) for t in toks):
        return False
    return common_share([_stripped(t) for t in toks]) >= min_common and not OWN_LINE.search(line)


def self_made(item):
    """True when this thing is LMemM observing itself (R26): its own files, data folders, logs and status."""
    title = (item.get("title") or "")
    if title.strip().lower() in OWN_FILES:
        return True
    ref = item.get("ref") or ""
    if any(ref.lower().endswith("/" + f) for f in OWN_FILES) or tasks.own_text(title):
        return True
    for ex in item.get("content", {}).get("excerpts", [])[-3:]:
        win = ((ex.get("source") or {}).get("window") or "")
        if win.strip().lower().split(" — ")[0] in OWN_FILES or OWN_PATH.search(ex.get("text", "")[:200]):
            return True
    return False


def own_line(line):
    return bool(OWN_LINE.search(line or "")) or tasks.own_text(line)


def fuzzy_has(text, phrase, ratio=0.84):
    """Whether `phrase` appears in `text` even with OCR slips ('Runnlng a command' still finds 'running a command')."""
    want = phrase.lower().split()
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9']+", text or "")]
    n = len(want)
    for i in range(len(words) - n + 1):
        if difflib.SequenceMatcher(None, " ".join(words[i:i + n]), phrase.lower()).ratio() >= ratio:
            return True
    return False


# ---------------------------------------------------------------- work threads

def _terms(item):
    """Distinctive words this thing is about: from its notes, a well-formed title, and well-formed words seen."""
    out = set()
    sources = [n["text"] for n in item.get("notes", [])]
    if clean_title(item):
        sources.append(item.get("title") or "")
    sources += [ex.get("text", "") for ex in item.get("content", {}).get("excerpts", [])]
    for text in sources:
        for tok in tokens(text):
            t = _stripped(tok)
            low = t.lower()
            if not t or not well_formed(t):
                continue
            if STRONG.match(low):
                out.add(("strong", re.sub(r"\d+$", "", low)))
            elif len(low) >= 5 and low.isalpha() and low not in ANCHOR_STOP:
                out.add(("weak", low))
    return out


def _weighty(item):
    return bool(item.get("notes")) or (item.get("seconds") or 0) >= WEIGHTY_SECONDS


def threads(items):
    """Group things into work threads. `items`: a list of items. Returns [{"items": [...], "maybe": [...]}], each list
    most recent first; `maybe` are things that might belong but are not shown to. Things that join nothing are alone."""
    items = list(items)
    terms = {i["id"]: _terms(i) for i in items}
    df = {}
    for ts in terms.values():
        for t in ts:
            df[t] = df.get(t, 0) + 1
    parent = {i["id"]: i["id"] for i in items}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    maybe_pairs = {}
    for n, a in enumerate(items):
        for b in items[n + 1:]:
            both = {t for t in terms[a["id"]] & terms[b["id"]] if df[t] <= MAX_DF}
            strong = {t for t in both if t[0] == "strong"}
            weak = {t for t in both if t[0] == "weak"}
            if strong:
                parent[find(a["id"])] = find(b["id"])
            elif len(weak) >= WEAK_LINK_TERMS and _weighty(a) and _weighty(b):
                maybe_pairs[(a["id"], b["id"])] = len(weak)         # shared ordinary words: possible, never enough (R28)
    groups = {}
    for i in items:
        groups.setdefault(find(i["id"]), []).append(i)
    out = []
    by_id = {i["id"]: i for i in items}
    for members in groups.values():
        ids = {m["id"] for m in members}
        members.sort(key=lambda m: m.get("last_seen", ""), reverse=True)
        maybe = {}
        for (x, y), n in maybe_pairs.items():
            for inside, outside in ((x, y), (y, x)):
                if inside in ids and outside not in ids:
                    maybe[outside] = max(maybe.get(outside, 0), n)
        out.append({"items": members, "maybe": [by_id[k] for k, _n in sorted(maybe.items(), key=lambda kv: -kv[1])]})
    return out


def scope_hits(item, scope):
    """How many places in this thing name the requested scope ('PR 25', or a project's words). OCR-garbled lines count
    only when the scope itself reads cleanly in them."""
    scope = (scope or "").strip()
    if not scope:
        return 0
    m = re.match(r"^(?:pr|pull request)\s*#?\s*(\d+)$", scope, re.I)
    pattern = re.compile(rf"\b(?:pr|pull request)\s*#?\s*-?0?{m.group(1)}\b", re.I) if m else None
    words = [w for w in re.findall(r"[a-z0-9]{3,}", scope.lower())]
    texts = [item.get("title") or "", item.get("ref") or ""] + [n["text"] for n in item.get("notes", [])]
    texts += [ex.get("text", "") for ex in item.get("content", {}).get("excerpts", [])]
    hits = 0
    for text in texts:
        low = text.lower()
        if (pattern and pattern.search(text)) or (not pattern and words and all(w in low for w in words)):
            hits += 1
    return hits


def last_signal(item, phrases=("running a command", "thinking")):
    """When an AI conversation last showed it was working ('Running a command'), as an ISO time, else None."""
    best = None
    for ex in item.get("content", {}).get("excerpts", []):
        if any(fuzzy_has(ex.get("text", ""), p) for p in phrases):
            at = ex.get("last_seen") or ex.get("first_seen")
            if at and (best is None or at > best):
                best = at
    return best


def parse(iso):
    try:
        return datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- what you typed (R32)

REQUEST_BUILD = re.compile(r"\b(code|build|implement|fix|add|make|create)\b", re.I)
REQUEST_RUN = re.compile(r"\b(run|test|try|check)\b", re.I)
REQUEST_ASK = re.compile(r"\?|\b(tell me|show me|why|how|what)\b", re.I)
CHOICE = re.compile(r"\b(lets|let's|go with|park|come with|follow)\b", re.I)
MIN_MESSAGE = 12
RUN_GAP = 90                                    # seconds without typing that starts a new message


def _local(iso):
    from trail_store import parse as parse_trail
    return parse_trail(iso).astimezone().replace(tzinfo=None)


def _common_prefix(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def authored_messages(events, items, now=None):
    """Messages you typed, whole and verbatim, from the trail's write events: [{"text", "at", "item", "chat", "project"}],
    oldest first. The trail records each keystroke burst as the sentences added so far, so a message is rebuilt by
    letting a longer version of the last sentence replace it. A new message starts when the field was cleared
    (the typed total drops) or after RUN_GAP seconds. Only events up to `now` are used."""
    spans = [(parse(i.get("first_seen")), parse(i.get("last_seen")), i) for i in items.values()]
    names = {}
    for e in events:
        if e.get("kind") == "focus":
            place = e.get("place") or {}
            if place.get("key") and place.get("name"):
                names[place["key"]] = place["name"]
    runs, last = [], {}
    for e in events:
        if e.get("kind") != "write" or not e.get("added"):
            continue
        try:
            at = _local(e["t"])
        except (KeyError, ValueError):
            continue
        if now and at > now:
            continue
        key = (e.get("place"), e.get("field"))
        prev = last.get(key)
        if not prev or e.get("total", 0) < prev["total"] or (at - prev["at"]).total_seconds() > RUN_GAP:
            run = {"place": e.get("place"), "app": e.get("app"), "sentences": [], "start": at}
            runs.append(run)
        else:
            run = prev["run"]
        for piece in e["added"]:
            piece = piece.strip()
            if not piece:
                continue
            sentences = run["sentences"]
            if sentences and piece.startswith(sentences[-1]):
                sentences[-1] = piece                                   # the same sentence, typed further
            elif sentences and sentences[-1].startswith(piece):
                continue
            elif sentences and _common_prefix(sentences[-1], piece) >= max(2, int(0.5 * min(len(piece), len(sentences[-1])))):
                sentences[-1] = piece                                   # a typo fixed in the sentence being typed
            else:
                sentences.append(piece)
        run["end"] = at
        last[key] = {"total": e.get("total", 0), "at": at, "run": run}
    out = []
    for run in runs:
        text = " ".join(run["sentences"]).strip()
        if len(text) < MIN_MESSAGE:
            continue
        if text[-1] not in ".?!":
            text += "…"                                                # as typed: the last words may not have been finished
        inside = [(b - a, i) for a, b, i in spans if a and b and i.get("app") == run["app"]
                  and a.timestamp() - 30 <= run["end"].timestamp() <= b.timestamp() + 30]
        item = min(inside, key=lambda x: x[0])[1] if inside else None
        chat = (run["place"] or "").split("thread=")[-1][-8:] or None
        project = (names.get(run["place"]) or "").rsplit(" - ", 1)[0] or None
        out.append({"text": text, "at": run["end"].isoformat(timespec="seconds"), "item": item["id"] if item else None,
                    "chat": chat, "project": project})
    return sorted(out, key=lambda m: m["at"])


def request_strength(text):
    """How much a message of yours reads as a request still open: build 3, run/test 2, ask 1, else 0."""
    if REQUEST_BUILD.search(text) and (CHOICE.search(text) or re.search(r"^\s*(please\s+)?(code|build|implement|fix|add|make|create)\b", text, re.I)):
        return 3
    if REQUEST_RUN.search(text):
        return 2
    return 1 if REQUEST_ASK.search(text) else 0


def request_sentence(text):
    """The sentence of a message that carries the request, to quote (with the choice that came just before it, if short)."""
    text = text.rstrip("…")
    parts = [p.strip() for p in re.split(r"(?<=[.?!])\s+", text) if p.strip()]
    for rx in (REQUEST_BUILD, REQUEST_RUN, REQUEST_ASK):
        n = next((k for k, p in enumerate(parts) if rx.search(p)), None)
        if n is not None:
            if n and len(parts[n]) < 40 and CHOICE.search(parts[n - 1]):
                return (parts[n - 1] + " " + parts[n]).rstrip(".")
            return parts[n].rstrip(".")
    return (parts[0] if parts else text).rstrip(".")
