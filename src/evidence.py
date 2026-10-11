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
  R28  Two things join one work thread only through shared distinctive words (3 or more, or one strong
       token such as 180dc), never through time, app switching, or a shared window. A glance of a few seconds
       with no note never joins on weak words.
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
    """Group things into work threads. `items`: a list of items. Returns [{"items": [...], "shared": [...]}], each list
    most recent first. Things that join nothing are returned alone."""
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

    shared_by = {}
    for n, a in enumerate(items):
        for b in items[n + 1:]:
            both = {t for t in terms[a["id"]] & terms[b["id"]] if df[t] <= MAX_DF}
            strong = {t for t in both if t[0] == "strong"}
            weak = {t for t in both if t[0] == "weak"}
            linked = bool(strong) or (len(weak) >= WEAK_LINK_TERMS and _weighty(a) and _weighty(b))
            if linked:
                parent[find(a["id"])] = find(b["id"])
                shared_by.setdefault(frozenset((a["id"], b["id"])), sorted(t[1] for t in strong | weak))
    groups = {}
    for i in items:
        groups.setdefault(find(i["id"]), []).append(i)
    out = []
    for members in groups.values():
        ids = {m["id"] for m in members}
        words = {}
        for pair, ws in shared_by.items():
            if pair <= ids:
                for w in ws:
                    words[w] = words.get(w, 0) + 1
        members.sort(key=lambda m: m.get("last_seen", ""), reverse=True)
        out.append({"items": members, "shared": [w for w, _n in sorted(words.items(), key=lambda kv: (-kv[1], kv[0]))][:6]})
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
