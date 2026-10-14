"""LMemM - where a remembered thing lives, so Resume can reopen that exact page or file. Plain functions, no UI.

    item["source"] = {"kind": "url" | "file", "value": ..., "app": ..., "title": ..., "seen": ISO time}

R36  An address is kept only when it is plain and safe to reopen: an http(s) page with no sign-in details in it, or a
     file on this Mac that a document app reported. Anything else is not kept, and Resume then says it has no address.
R37  It is kept only from frames LMemM was allowed to keep: skipped apps, private windows and sensitive sites never
     get this far (tracker._capture). It lives in the thing's own entry, so forgetting the thing forgets the address.
R38  It is never sent to a model. Resume reopens it with `open`, on this Mac, when you press the button.
R39  Before reopening, it is checked again: a web address must still be well-formed; a file must still exist. If not,
     Resume says so and keeps the saved title; it does not fall back to a guess.
"""

import os
import re
from urllib.parse import parse_qsl, unquote, urlsplit

MAX_URL = 2000
SECRET_PARAMS = re.compile(r"^(?:access_?token|id_?token|refresh_?token|token|auth|authorization|password|passwd|pwd|secret|"
                           r"api_?key|apikey|session|sessionid|sid|code|otp|signature|sig)$", re.I)
PRIVATE_DIRS = (".ssh", ".gnupg", ".aws", "Keychains", ".config/gcloud", ".kube", ".docker")
SKIP_SITES = None                       # set from config on first use (config imports no Mac modules, but keep this file light)


def _skip_sites():
    global SKIP_SITES
    if SKIP_SITES is None:
        import config
        SKIP_SITES = config.SKIP_SITES
    return SKIP_SITES


def clean_url(url):
    """The address as it should be kept, or None. Only http(s); no user:password; no token-like query values; no
    spaces or control characters; and nothing on a site LMemM is told to skip."""
    if not isinstance(url, str):
        return None
    url = url.strip()
    if not url or len(url) > MAX_URL or re.search(r"[\s\x00-\x1f\x7f]", url):
        return None
    if not re.match(r"^https?://", url, re.I):
        return None
    try:
        parts = urlsplit(url)
        host = parts.hostname
        queries = parse_qsl(parts.query, keep_blank_values=True)
    except ValueError:
        return None
    if not host or "." not in host and host != "localhost":
        return None
    if parts.username or parts.password:
        return None
    if any(SECRET_PARAMS.match(k) and v for k, v in queries):
        return None
    if _skip_sites().search(url):
        return None
    return url


def safe_path(path):
    """A local path that may be kept and reopened: absolute, no '..', no control characters, no private folders."""
    if not isinstance(path, str) or not path.startswith("/") or len(path) > MAX_URL:
        return None
    if re.search(r"[\x00-\x1f\x7f]", path) or ".." in path.split("/"):
        return None
    if any(f"/{d}/" in path + "/" for d in PRIVATE_DIRS):
        return None
    return path


def file_path(doc):
    """The local path of a document an app reported (a file:// address), or None."""
    if not isinstance(doc, str) or not doc.lower().startswith("file://"):
        return None
    return safe_path(unquote(urlsplit(doc).path))


def from_meta(meta):
    """What one captured frame says about where it came from, or None."""
    app, title = meta.get("app"), meta.get("tab_title") or meta.get("window")
    url = clean_url(meta.get("url"))
    if url:
        return {"kind": "url", "value": url, "app": app, "title": title, "seen": meta.get("iso")}
    path = file_path(meta.get("file"))
    if path:
        return {"kind": "file", "value": path, "app": app, "title": title, "seen": meta.get("iso")}
    return None


def remember(item, meta):
    """Keep the newest address on the item. A frame with none leaves the old one alone (a tab you left is not erased)."""
    found = from_meta(meta)
    if found:
        item["source"] = found
    return bool(found)


def check(source, exists=os.path.exists):
    """-> (ok, problem). R39: well-formed now, and a file still there."""
    if not isinstance(source, dict):
        return False, "no address was saved"
    if source.get("kind") == "url":
        return (True, None) if clean_url(source.get("value")) else (False, "the saved address is no longer a safe web address")
    if source.get("kind") == "file":
        path = source.get("value")
        if not safe_path(path):
            return False, "the saved file location is not usable"
        return (True, None) if exists(path) else (False, "that file isn't at its saved location any more")
    return False, "no address was saved"
