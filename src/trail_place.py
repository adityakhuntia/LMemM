"""LMemM - which place is this? A chat, an AI conversation, an email, a doc, a page, a file.

Pure rules over a Snapshot (trail_ax.py) plus the app and URL, so they are tested everywhere.

The old weakness was that two chats in one app, or two conversations in one browser tab, looked
the same: the window title is just "WhatsApp" or "ChatGPT". Three things fix it:

  1. URLs that carry an id name the place exactly (ChatGPT /c/<id>, Slack /client/<team>/<channel>,
     a Google Doc /d/<id>, a Gmail thread, a GitHub PR). No guessing.
  2. Without an id (WhatsApp, Messages, Telegram, Teams...) the name comes from several signals
     that are weighed together: the label of the message box ("Type a message to Mum"), the
     selected row of the sidebar, the page heading and the window title. Agreement raises
     confidence; disagreement is reported, not hidden.
  3. A low-confidence read never flips the current place (see PlaceTracker), so a half-loaded
     screen does not invent a switch.

place(...) returns a dict: key, kind, name, service, container, url, confidence, signals, conflict.
"""

import re
import unicodedata
from urllib.parse import parse_qs, urlparse

import config

KINDS = ("chat", "ai_chat", "email", "doc", "page", "code", "terminal", "files", "app")

_BADGE = re.compile(r"^\s*[\(\[]\d[\d,+]*[\)\]]\s*|\s*[\(\[]\d[\d,+]*[\)\]]\s*$|^\s*[•●·*]\s*")
_INVISIBLE = re.compile(r"[​-‏‪-‮⁠﻿]")


def display(text):
    """A name as shown: unread badges and invisible marks removed, spaces collapsed."""
    t = _INVISIBLE.sub("", unicodedata.normalize("NFKC", text or ""))
    t = _BADGE.sub("", t)
    return " ".join(t.split()).strip(" -–—|")


def norm(text):
    return display(text).casefold()


# ---------------------------------------------------------------- URLs that name a place

# (host regex, path-or-fragment regex, kind, service, groups that make the id, groups that name the container)
ROUTES = [
    (r"(^|\.)(chatgpt\.com|chat\.openai\.com)$", r"^/(?:g/[^/]+/)?c/([\w-]{8,})", "ai_chat", "ChatGPT"),
    (r"(^|\.)claude\.ai$", r"^/chat/([\w-]{8,})", "ai_chat", "Claude"),
    (r"(^|\.)claude\.ai$", r"^/project/([\w-]{8,})", "ai_chat", "Claude project"),
    (r"(^|\.)gemini\.google\.com$", r"^/(?:gem/[\w-]+/)?app/([\w-]{8,})", "ai_chat", "Gemini"),
    (r"(^|\.)perplexity\.ai$", r"^/search/([\w-]+)", "ai_chat", "Perplexity"),
    (r"(^|\.)app\.slack\.com$", r"^/client/(T\w+)/(\w+)", "chat", "Slack"),
    (r"(^|\.)discord\.com$", r"^/channels/(@me|\d+)/(\d+)", "chat", "Discord"),
    (r"(^|\.)linkedin\.com$", r"^/messaging/thread/([\w=%-]+)", "chat", "LinkedIn"),
    (r"(^|\.)(x|twitter)\.com$", r"^/messages/([\w-]+)", "chat", "X"),
    (r"(^|\.)web\.telegram\.org$", r"^/[ak]/?#(-?[\w@]+)", "chat", "Telegram", "frag"),
    (r"(^|\.)mail\.google\.com$", r"^#(?:inbox|sent|starred|all|drafts|label/[^/]+|search/[^/]+|imp|spam|trash)/([A-Za-z0-9]{16,})",
     "email", "Gmail", "frag"),
    (r"(^|\.)outlook\.(office|live)\.com$", r"/id/([\w%-]{16,})", "email", "Outlook"),
    (r"(^|\.)docs\.google\.com$", r"^/(?:document|spreadsheets|presentation|forms)/d/([\w-]{20,})", "doc", "Google Docs"),
    (r"(^|\.)notion\.(so|site)$", r"([0-9a-f]{32})(?:[?#]|$)", "doc", "Notion"),
    (r"(^|\.)figma\.com$", r"^/(?:file|design|board)/(\w+)", "doc", "Figma"),
    (r"(^|\.)github\.com$", r"^/([\w.-]+/[\w.-]+/(?:pull|issues)/\d+)", "page", "GitHub"),
    (r"(^|\.)linear\.app$", r"^/([\w-]+/issue/[\w-]+)", "page", "Linear"),
    (r"(^|\.)youtube\.com$", r"^/watch", "page", "YouTube", "query:v"),
]
WEB_CHATS_WITHOUT_ID = {"web.whatsapp.com": "WhatsApp", "web.telegram.org": "Telegram",
                        "teams.microsoft.com": "Teams", "teams.live.com": "Teams",
                        "messages.google.com": "Messages", "www.messenger.com": "Messenger",
                        "app.slack.com": "Slack"}
AI_WITHOUT_ID = {"chatgpt.com": "ChatGPT", "chat.openai.com": "ChatGPT", "claude.ai": "Claude",
                 "gemini.google.com": "Gemini", "perplexity.ai": "Perplexity"}
FRAGMENT_HOSTS = {"mail.google.com", "web.telegram.org"}   # where the fragment is the address
KEEP_QUERY = {"v", "q", "id", "p", "t", "list"}      # the few query keys that change which page it is


def parse_url(url):
    """(host, path, fragment, query dict) of a URL, or None."""
    try:
        u = urlparse(url if "://" in url else "https://" + url)
        return (u.hostname or "").lower(), u.path or "/", u.fragment, parse_qs(u.query)
    except ValueError:
        return None


def route(url):
    """{kind, service, id} when the URL itself names the place, else None."""
    if not url:
        return None
    parsed = parse_url(url)
    if not parsed or not parsed[0]:
        return None
    host, path, frag, query = parsed
    for r in ROUTES:
        host_re, loc_re, kind, service = r[:4]
        mode = r[4] if len(r) > 4 else "path"
        if not re.search(host_re, host):
            continue
        if mode == "frag":
            m = re.search(loc_re, "#" + frag) if frag else None
        elif mode.startswith("query:"):
            m = re.search(loc_re, path)
            if m and query.get(mode[6:]):
                return {"kind": kind, "service": service, "id": f"{host}:{query[mode[6:]][0]}"}
            m = None
        else:
            m = re.search(loc_re, path)
        if m:
            ident = "/".join(g for g in m.groups() if g) or (m.group(0))
            if service == "Google Docs" and "gid=" in frag:
                ident += "#" + re.search(r"gid=(\d+)", frag).group(1)      # which sheet tab
            return {"kind": kind, "service": service, "id": ident}
    return None


def page_id(url):
    """host + path (+ the few query keys that matter) of an ordinary page."""
    parsed = parse_url(url)
    if not parsed:
        return ""
    host, path, _frag, query = parsed
    keep = "&".join(f"{k}={query[k][0]}" for k in sorted(query) if k in KEEP_QUERY)
    return f"{host}{path.rstrip('/') or '/'}" + (f"?{keep}" if keep else "")


# ---------------------------------------------------------------- native app profiles

# bundle id (or app name) -> how to read a chat name. `box`: regex over the message box's label;
# `title`: regex over the window title; `drop`: a suffix the title carries.
PROFILES = {
    "net.whatsapp.WhatsApp": {"service": "WhatsApp", "kind": "chat", "box": r"(?i)^type a message(?: to)?\s+(.+)$",
                              "title": r"^(?!WhatsApp$)(.+?)(?: - WhatsApp)?$"},
    "WhatsApp": {"service": "WhatsApp", "kind": "chat", "box": r"(?i)^type a message(?: to)?\s+(.+)$"},
    "com.apple.MobileSMS": {"service": "Messages", "kind": "chat", "box": r"(?i)^(?:i?message|text message|sms)(?: to)?\s*[-:·]?\s*(.+)?$",
                            "title": r"^(?!Messages$)(.+?)(?: - Messages)?$"},
    "com.tinyspeck.slackmacgap": {"service": "Slack", "kind": "chat", "box": r"(?i)^message\s+(.+)$",
                                  "title": r"^(.+?)(?: \((?:Channel|DM|Direct Message|Huddle)\))?(?: - [^-]+)?(?: - \d+ new items?)? - Slack$"},
    "com.hnc.Discord": {"service": "Discord", "kind": "chat", "box": r"(?i)^message\s+(.+)$",
                        "title": r"^(?:\(\d+\)\s*)?(.+?) \| .+ - Discord$|^(?:\(\d+\)\s*)?(.+?) - Discord$"},
    "ru.keepcoder.Telegram": {"service": "Telegram", "kind": "chat", "box": r"(?i)^(?:write a )?message(?: to)?\s*(.+)?$"},
    "org.whispersystems.signal-desktop": {"service": "Signal", "kind": "chat", "box": r"(?i)^send a message(?: to)?\s*(.+)?$"},
    "com.microsoft.teams2": {"service": "Teams", "kind": "chat", "box": r"(?i)^(?:type a message|reply)(?: to)?\s*(.+)?$",
                             "title": r"^(.+?) \| Microsoft Teams$"},
    "com.openai.chat": {"service": "ChatGPT", "kind": "ai_chat", "title": r"^(?!ChatGPT$)(.+?)(?: - ChatGPT)?$"},
    "com.anthropic.claudefordesktop": {"service": "Claude", "kind": "ai_chat", "title": r"^(?!Claude$)(.+?)(?: - Claude)?$"},
    "com.apple.mail": {"service": "Mail", "kind": "email", "title": r"^(.+?)(?: [-–] (?:Inbox|Sent|Drafts).*)?$"},
    "com.apple.Notes": {"service": "Notes", "kind": "doc", "title": r"^(.+)$"},
    "com.apple.dt.Xcode": {"service": "Xcode", "kind": "code", "title": r"^(.+?)(?: [-—–] .+)?$"},
    "com.microsoft.VSCode": {"service": "VS Code", "kind": "code", "title": r"^(?:● )?(.+?)(?: [—–-] (.+?))?(?: [—–-] Visual Studio Code)?$"},
    "com.todesktop.230313mzl4w4u92": {"service": "Cursor", "kind": "code", "title": r"^(?:● )?(.+?)(?: [—–-] (.+?))?(?: [—–-] Cursor)?$"},
    "com.apple.Terminal": {"service": "Terminal", "kind": "terminal", "title": r"^(.+)$"},
    "com.googlecode.iterm2": {"service": "iTerm", "kind": "terminal", "title": r"^(.+)$"},
    "com.apple.finder": {"service": "Finder", "kind": "files", "title": r"^(.+)$"},
}
BOX_FALLBACK = re.compile(r"(?i)^(?:type a message|write a message|send a message|message|reply|imessage|text message)"
                          r"(?:\s+(?:to|in)\b)?\s*[-:·]?\s*(.*)$")
AI_BOX = re.compile(r"(?i)^(?:ask|how can i help|message (?:chatgpt|claude)|reply to claude|send a message to|"
                    r"enter a prompt|write your prompt|talk to)")
APP_SUFFIX = re.compile(r"\s*[-–—|·]\s*(?:Google Chrome|Brave|Microsoft Edge|Arc|Safari|Chromium|Firefox)\s*(?:[-–—]\s*\S+)?$")


def _title_name(profile, title):
    pat = profile.get("title") if profile else None
    if not pat or not title:
        return None, None
    m = re.match(pat, title)
    if not m:
        return None, None
    groups = [g for g in m.groups() if g]
    return (display(groups[0]), display(groups[1]) if len(groups) > 1 else None) if groups else (None, None)


def _box_name(profile, label):
    if not label:
        return None
    for pat in (profile.get("box") if profile else None, None):
        rx = re.compile(pat) if pat else BOX_FALLBACK
        m = rx.match(label)
        if m:
            name = display(m.group(1)) if m.groups() and m.group(1) else ""
            return name.lstrip("#@") and name or None
    return None


def _same(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b) and (a == b or (len(a) >= 3 and len(b) >= 3 and (a in b or b in a)))


WEIGHTS = {"box": 3, "selected": 3, "heading": 2, "title": 2, "tab": 1}


def resolve_name(cands):
    """cands: [(signal, name)]. -> (name, confidence 0-1, signals that agree, conflict?)."""
    groups = []                                  # [{"name", "w", "signals"}]
    for signal, name in cands:
        name = display(name)
        if not name:
            continue
        for g in groups:
            if _same(g["name"], name):
                g["w"] += WEIGHTS.get(signal, 1)
                g["signals"].append(signal)
                if len(name) < len(g["name"]) and len(name) >= 3:
                    g["name"] = name            # the shorter form is the cleaner name
                break
        else:
            groups.append({"name": name, "w": WEIGHTS.get(signal, 1), "signals": [signal]})
    if not groups:
        return None, 0.0, [], False
    groups.sort(key=lambda g: -g["w"])
    best = groups[0]
    strong_others = [g for g in groups[1:] if g["w"] >= 2]
    conflict = bool(strong_others) and strong_others[0]["w"] >= best["w"] - 1
    conf = min(1.0, 0.35 + 0.2 * best["w"]) if len(best["signals"]) > 1 else min(0.8, 0.25 + 0.18 * best["w"])
    if conflict:
        conf = min(conf, 0.45)
    return best["name"], round(conf, 2), best["signals"], conflict


# ---------------------------------------------------------------- the place

def place(app, bundle_id, snap, url=None):
    """What `snap` (a trail_ax.Snapshot or None) says about where the user is."""
    url = (url or (snap.url if snap else "") or "").strip()
    title = display(snap.title) if snap else ""
    label = snap.focus_label if snap else ""
    profile = PROFILES.get(bundle_id) or PROFILES.get(app)
    host = (parse_url(url) or ("",))[0] if url.startswith(("http://", "https://")) or "." in url.split("/")[0] else ""
    in_browser = app in config.BROWSERS or (bundle_id or "").startswith(("com.google.Chrome", "com.apple.Safari",
                                                                          "com.brave", "com.microsoft.edgemac", "company.thebrowser"))
    r = route(url) if in_browser or host else None
    out = {"app": app, "bundle_id": bundle_id, "url": _clean_url(url) if url else "", "service": app,
           "kind": "app", "name": title or app, "container": None, "confidence": 0.3, "signals": [], "conflict": False}

    web_chat = WEB_CHATS_WITHOUT_ID.get(host) if in_browser else None
    web_ai = AI_WITHOUT_ID.get(host) if in_browser else None
    if r:
        out.update(kind=r["kind"], service=r["service"], confidence=1.0, signals=["url"])
        out["key"] = f'{r["service"]}:{r["kind"]}:{r["id"]}'
        out["name"] = display(APP_SUFFIX.sub("", title)) or r["service"]
        if r["kind"] == "chat" and r["service"] in {"Slack", "Discord"}:
            n, _c, _sig, _conflict = _chat_name(profile or PROFILES.get("com.tinyspeck.slackmacgap"), snap, title, label)
            out["name"] = n or out["name"]
        return out
    if web_chat or (profile and profile.get("kind") in {"chat", "ai_chat"}) or (not profile and _box_says_chat(label)):
        service = web_chat or (profile or {}).get("service") or app
        kind = (profile or {}).get("kind", "chat")
        if web_ai:
            kind = "ai_chat"
        name, conf, sig, conflict = _chat_name(profile, snap, title, label, web_title=in_browser)
        out.update(kind=kind, service=service, name=name or service, confidence=conf if name else 0.2,
                   signals=sig, conflict=conflict)
        out["key"] = f"{service}:{kind}:{norm(name)}" if name else f"{service}:{kind}:?"
        return out
    if web_ai:
        # an AI site with no conversation id yet: a new conversation
        out.update(kind="ai_chat", service=web_ai, name=display(APP_SUFFIX.sub("", title)) or web_ai, confidence=0.7,
                   signals=["url"])
        out["key"] = f"{web_ai}:ai_chat:new"
        return out
    if in_browser and url:
        name = display(APP_SUFFIX.sub("", title)) or host
        out.update(kind="page", service=host, name=name, confidence=0.9, signals=["url"], url=_clean_url(url))
        out["key"] = f"page:{page_id(url)}"
        return out
    if profile:
        name, container = _title_name(profile, title)
        kind = profile["kind"]
        if kind == "code" and container:
            out["container"] = container
        out.update(kind=kind, service=profile["service"], name=name or title or profile["service"],
                   confidence=0.8 if name else 0.4, signals=["title"] if name else [])
        out["key"] = f'{profile["service"]}:{kind}:{norm(container or "")}/{norm(out["name"])}'
        return out
    doc = url if url and not in_browser else ""
    out.update(kind="doc" if doc else "app", name=title or app, confidence=0.8 if doc else 0.5 if title else 0.2,
               signals=(["document"] if doc else ["title"] if title else []))
    out["key"] = f"{bundle_id or app}:{'doc:' + doc if doc else 'win:' + norm(title)}"
    return out


def _box_says_chat(label):
    return bool(label) and (bool(BOX_FALLBACK.match(label)) or bool(AI_BOX.match(label)))


def _chat_name(profile, snap, title, label, web_title=False):
    cands = []
    n = _box_name(profile, label)
    if n:
        cands.append(("box", n))
    if snap:
        for row in snap.selected:
            if row:
                cands.append(("selected", row[0]))
        for h in snap.headings[:2]:
            cands.append(("heading", h))
    t, _c = _title_name(profile, title)
    if t and not (web_title and t.casefold() in {"whatsapp", "telegram", "messages", "slack", "teams"}):
        cands.append(("title", t))
    return resolve_name(cands)


def _clean_url(url):
    parsed = parse_url(url)
    if not parsed:
        return ""
    host, path, frag, query = parsed
    keep = "&".join(f"{k}={query[k][0]}" for k in sorted(query) if k in KEEP_QUERY)
    return f"{host}{path}" + (f"?{keep}" if keep else "") + (f"#{frag}" if frag and host in FRAGMENT_HOSTS else "")


# ---------------------------------------------------------------- settling

class PlaceTracker:
    """Turns a stream of reads into place changes without flicker.

    A new place is accepted at once when it is certain (a URL id, or two signals agree) or the
    app changed. A shaky one has to repeat, or stay for `settle_ms`, before it counts. A read
    that cannot name a chat never replaces a known chat in the same app."""

    def __init__(self, settle_ms=150):
        self.settle_ms = settle_ms
        self.current = None
        self.cand = None
        self.cand_since = 0
        self.since = 0

    def pending_ms(self, now_ms):
        """Milliseconds until a waiting candidate would be accepted, or None."""
        return None if self.cand is None else max(0, self.cand_since + self.settle_ms - now_ms)

    def update(self, p, now_ms):
        """-> the place to announce (a dict with `from_key` and `dwell_ms`), or None."""
        cur = self.current
        if cur is not None and p["key"] == cur["key"]:
            self.cand = None
            for k in ("name", "confidence", "signals", "conflict", "url"):
                cur[k] = p[k]
            return None
        if cur is not None and p["key"].endswith(":?") and p["app"] == cur["app"] and cur["kind"] == p["kind"]:
            self.cand = None                                   # unreadable: keep what we knew
            return None
        sure = cur is None or p["app"] != cur["app"] or p["confidence"] >= 0.8
        if not sure:
            if self.cand is None or self.cand["key"] != p["key"]:
                self.cand, self.cand_since = p, now_ms
                return None
            if now_ms - self.cand_since < self.settle_ms:
                return None
        self.cand = None
        out = dict(p, from_key=cur["key"] if cur else None, dwell_ms=now_ms - self.since if cur else 0)
        self.current, self.since = p, now_ms
        return out
