"""Identity is structural, never guessed from titles; no files are read."""
import dataclasses
import hashlib
import json
import posixpath
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

def identifier(kind, value):
    return kind + "-" + hashlib.sha256(value.encode()).hexdigest()[:24]

def utc(value):
    t = datetime.fromisoformat(value)
    if t.tzinfo is None:
        raise ValueError("Timezone required")
    return t.astimezone(timezone.utc).isoformat()

def origin(url):
    p = urlsplit(url)
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
        raise ValueError("Invalid browser locator")
    host = p.hostname.lower()
    port = p.port
    netloc = ("[" + host + "]") if ":" in host else host
    if port and not ((p.scheme == "http" and port == 80) or (p.scheme == "https" and port == 443)):
        netloc += ":" + str(port)
    return p.scheme + "://" + netloc

def canonical_url(url):
    p = urlsplit(url)
    base = urlsplit(origin(url))
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "fbclid"}]
    return urlunsplit((base.scheme, base.netloc, p.path or "/", urlencode(query), ""))

def canonical_path(value):
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
        raise ValueError("Absolute local locator required")
    return posixpath.normpath(value)

def canonical_identity(envelope):
    if not envelope.identity_authoritative:
        return None, None
    if envelope.artifact_locator.startswith(("http://", "https://")):
        return None, identifier("artifact", canonical_url(envelope.artifact_locator))
    path = canonical_path(envelope.artifact_locator)
    workspace = canonical_path(envelope.workspace_locator) if envelope.workspace_locator else None
    if workspace and path != workspace and not path.startswith(workspace.rstrip("/") + "/"):
        raise ValueError("Artifact is outside workspace")
    return (identifier("project", workspace) if workspace else None, identifier("artifact", path))

def validate_source(envelope, policy):
    if envelope.app_id not in policy.allowed_apps or envelope.policy_revision != policy.revision:
        raise ValueError("Source not permitted by current policy")
    if envelope.private_context or not envelope.browser_context_known:
        raise ValueError("Private or unknown source context")
    for value in (envelope.source_id, envelope.session_id, envelope.app_id, envelope.artifact_locator):
        if not isinstance(value, str) or not value or len(value.encode()) > 4096 or "\x00" in value:
            raise ValueError("Invalid source field")
    browser = envelope.artifact_locator.startswith(("http://", "https://"))
    if envelope.app_id != "com.microsoft.VSCode" and not browser:
        raise ValueError("Browser source requires URL")
    if browser:
        site = origin(envelope.artifact_locator)
        if site not in policy.allowed_origins or site in policy.denied_origins:
            raise ValueError("Browser origin not permitted")
    if envelope.origin_type not in {"user_note", "observed_screen_text", "trusted_artifact_snapshot"}:
        raise ValueError("Unsupported source origin")
    if not isinstance(envelope.identity_authoritative, bool) or len(envelope.spans) > 64:
        raise ValueError("Invalid identity or span count")
    utc(envelope.at)
    ids = set()
    spans = []
    for span in envelope.spans:
        if not isinstance(span.text, str) or not span.span_id or span.span_id in ids or len(span.span_id) > 256:
            raise ValueError("Invalid span")
        ids.add(span.span_id)
        raw = span.text.encode()
        text = raw[:4096].decode("utf-8", errors="ignore")
        spans.append(dataclasses.replace(span, text=text, truncated=span.truncated or len(raw) > 4096))
    canonical_identity(envelope)
    return dataclasses.replace(envelope, at=utc(envelope.at), spans=tuple(spans))


def references_project(text,locator):
    """An exact project path or contained file, never a similarly named prefix."""
    import re
    return bool(re.search(r'(?<![\w/.-])'+re.escape(locator)+r'(?=/|[\s,.;:!?)]|$)',text))
