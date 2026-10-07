"""Private interaction summaries, capture links and reconstructable session evidence."""

import copy
import json
import hashlib
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from memory_content import remember_content


def _now():
    return datetime.now(timezone.utc).isoformat()


def _session(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise ValueError("invalid session ID")
    return value


def private_write(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_name(path.name + ".tmp")
    fd = os.open(temp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(doc, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def fingerprint(items):
    return hashlib.sha256(json.dumps(items, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read_json(path):
    with Path(path).open() as stream:
        return json.load(stream)


def prune_corpus(root, now=None, skip=None):
    root = Path(root)
    now = now or _now()
    for other in (root / "inputs").glob("*.json"):
        if other == skip:
            continue
        doc = read_json(other)
        limit = min(doc.get("retention_hours", 24), 24)
        cutoff = datetime.fromisoformat(now) - timedelta(hours=limit)
        events = [e for e in doc["events"] if datetime.fromisoformat(e["end_utc"]) >= cutoff]
        doc["expired"] = doc.get("expired", 0) + len(doc["events"]) - len(events)
        doc["events"] = events
        doc["captures"] = [c for c in doc.get("captures", []) if datetime.fromisoformat(c.get("at", now)) >= cutoff]
        live = {c["id"] for c in doc["captures"]}
        for frame in (root / "inputs" / "frames" / other.stem).glob("*.jpg"):
            if frame.stem not in live:
                frame.unlink()
        private_write(other, doc)


class InputStore:
    def __init__(self, session_id, root, retention_hours=24, clock=_now):
        _session(session_id)
        if not 0 < retention_hours <= 24:
            raise ValueError("input retention must be between 0 and 24 hours")
        self.root = Path(root)
        recover_deletion(self.root)
        self.session_id = session_id
        self.path = self.root / "inputs" / (session_id + ".json")
        self.contribution = self.root / "contributions" / (session_id + ".json")
        self.retention_hours = retention_hours
        self.clock = clock
        self.closed = False
        self.start_items = {}
        self.observed = {}
        self.observed_first = {}
        self.observed_pins = set()
        self.observed_refs = {}
        self.doc = read_json(self.path) if self.path.exists() else {
            "schema_version": 1, "session": session_id, "events": [], "captures": [], "status": {"state": "off"}, "expired": 0}
        if not isinstance(self.doc, dict) or self.doc.get("session") != session_id or not isinstance(self.doc.get("events"), list):
            raise ValueError("invalid input store")
        self._prune()
        self._save()
        prune_corpus(self.root, self.clock(), skip=self.path)

    def _save(self):
        if self.closed:
            raise RuntimeError("session input store is closed")
        self.doc["retention_hours"] = self.retention_hours
        private_write(self.path, self.doc)

    def _prune(self):
        cutoff = datetime.fromisoformat(self.clock()) - timedelta(hours=self.retention_hours)
        kept = [e for e in self.doc["events"] if datetime.fromisoformat(e["end_utc"]) >= cutoff]
        self.doc["expired"] += len(self.doc["events"]) - len(kept)
        self.doc["dropped_capacity"] = self.doc.get("dropped_capacity", 0) + max(0, len(kept) - 4096)
        self.doc["events"] = kept[-4096:]
        self.doc["captures"] = [c for c in self.doc["captures"] if datetime.fromisoformat(c.get("at", self.clock())) >= cutoff][-4096:]
        live = {c["id"] for c in self.doc["captures"]}
        frames = self.root / "inputs" / "frames" / self.session_id
        for path in frames.glob("*.jpg"):
            if path.stem not in live:
                path.unlink()

    def append(self, summaries):
        allowed = {"event_id", "sequence", "kind", "context_id", "start_offset_ns", "end_offset_ns",
                   "start_utc", "end_utc", "payload"}
        for event in summaries:
            if set(event) != allowed:
                raise ValueError("unknown interaction fields")
            payloads = {"keyboard_activity": {"count"}, "pointer_movement": {"from", "to", "drag"},
                        "click": {"region", "button"}, "scroll": {"direction", "magnitude"}, "gap": {"reason"},
                        "context_transition": {"from", "to"}, "context_exit": {"from"},
                        "navigation_shortcut": {"action", "direction", "count"}}
            if event["kind"] not in payloads or set(event["payload"]) != payloads[event["kind"]]:
                raise ValueError("unknown interaction payload")
        self.doc["events"].extend(copy.deepcopy(summaries))
        self._prune()
        self._save()

    def confirm_navigation(self, transitions):
        for transition in transitions:
            if transition["kind"] not in {"context_transition", "context_exit"}:
                continue
            for event in self.doc["events"]:
                age = transition["start_offset_ns"] - event["end_offset_ns"]
                if event["kind"] == "navigation_shortcut" and "observed_transition" not in event and event["context_id"] == transition["payload"]["from"] and 0 <= age <= 2_000_000_000:
                    allowed_gaps = {"context_change", "context_boundary"}
                    if transition["kind"] == "context_exit":
                        allowed_gaps.add("excluded_or_missing_window")
                    if any(e["kind"] == "gap" and event["sequence"] < e["sequence"] < transition["sequence"] and e["payload"]["reason"] not in allowed_gaps for e in self.doc["events"]):
                        continue
                    event["observed_transition"] = transition["event_id"]
                    event["observed_result"] = "left_allowed_app" if transition["kind"] == "context_exit" else "allowed_context_changed"
        self._save()

    def link_capture(self, capture_id, context_id, start_ns, end_ns, item_id=None):
        if self.closed:
            return []
        for event in self.doc["events"]:
            if event["context_id"] != context_id or event["end_offset_ns"] > start_ns or event.get("link_status") == "gap":
                continue
            if "after_capture" not in event:
                event["after_capture"] = capture_id
                prior = next((c for c in reversed(self.doc["captures"]) if c["id"] != capture_id and c["context_id"] == context_id
                              and c.get("eligible", True) and c["end_ns"] <= event["start_offset_ns"]), None)
                if prior:
                    event["before_capture"] = prior["id"]
                    event["before_age_seconds"] = round((event["start_offset_ns"] - prior["end_ns"]) / 1e9, 3)
            if event.get("after_capture") == capture_id and item_id:
                event["item"] = item_id
        if not any(c["id"] == capture_id for c in self.doc["captures"]):
            self.doc["captures"].append({"id": capture_id, "context_id": context_id, "start_ns": start_ns, "end_ns": end_ns, "at": self.clock()})
        self.doc["captures"] = self.doc["captures"][-4096:]
        self._save()
        return [e["event_id"] for e in self.doc["events"] if e.get("after_capture") == capture_id]

    def keep_capture(self, capture_id, path):
        if not re.fullmatch(r"\d{8}-\d{6}", capture_id):
            raise ValueError("invalid capture ID")
        destination = self.root / "inputs" / "frames" / self.session_id / (capture_id + ".jpg")
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(path, destination)
        destination.chmod(0o600)

    def invalidate_context(self, reason):
        # Already verified persisted events stay; no cross-boundary capture may link them.
        for event in self.doc["events"]:
            if "after_capture" not in event:
                event["link_status"] = "gap"
        for capture in self.doc["captures"]:
            capture["eligible"] = False
        self.doc["status"]["gap"] = reason
        self._save()

    def status(self):
        return dict(self.doc["status"], records=len(self.doc["events"]), expired=self.doc["expired"])

    def set_status(self, status):
        self.doc["status"] = dict(status)
        self._save()

    def read(self):
        self._prune()
        self._save()
        prune_corpus(self.root, self.clock(), skip=self.path)
        return copy.deepcopy(self.doc)

    def initialize_baseline(self, items):
        base = self.root / "contributions" / "baseline.json"
        if not base.exists():
            private_write(base, {"schema_version": 1, "items": items})
        self.start_items = copy.deepcopy(items)

    def observe(self, item_id, content, meta=None, pinned=False, ref=None):
        if meta:
            self.observed_first.setdefault(item_id, meta["iso"])
        if pinned:
            self.observed_pins.add(item_id)
        if ref:
            self.observed_refs.setdefault(item_id, set()).add(ref)
        if content is not None:
            remember_content(self.observed.setdefault(item_id, {}), content)

    def checkpoint(self, items, events, notes):
        if self.closed:
            raise RuntimeError("session evidence store is closed")
        touched = {e["item"] for e in events} | {n["item"] for n in notes if n.get("item")}
        touched.update(iid for iid, value in items.items()
                       if value.get("notes_done", {}) != self.start_items.get(iid, {}).get("notes_done", {}))
        if not events and not notes:  # useful when importing independently owned evidence
            touched = {iid for iid in items if items[iid] != self.start_items.get(iid)}
        contributions = {}
        for iid in touched:
            current = items[iid]
            original = self.start_items.get(iid, {})
            delta = {k: current.get(k, 0) - original.get(k, 0) for k in ("seconds", "visits", "updates")}
            activity = {}
            for kind, value in current.get("activity", {}).items():
                old = original.get("activity", {}).get(kind, {})
                activity[kind] = {"seconds": value.get("seconds", 0) - old.get("seconds", 0),
                                  "count": value.get("count", 0) - old.get("count", 0),
                                  "text": [t for t in value.get("text", []) if t not in old.get("text", [])]}
            metadata = {k: copy.deepcopy(v) for k, v in current.items() if k not in {"activity", "content", "notes", "seconds", "visits", "updates", "first_seen", "pinned", "refs", "typing_area"}}
            metadata["notes_done"] = copy.deepcopy(current.get("notes_done", {}))
            metadata["first_seen"] = self.observed_first.get(iid, current["last_seen"])
            metadata["refs"] = sorted(self.observed_refs.get(iid, {current.get("ref")} ) - {None})
            if iid in self.observed_pins:
                metadata["pinned"] = True
            contributions[iid] = {"metadata": metadata, "delta": delta, "activity": activity,
                                  "notes": [n for n in current.get("notes", []) if n not in original.get("notes", [])],
                                  "content": self.observed.get(iid, {}).get("content", {})}
        private_write(self.contribution, {"schema_version": 1, "session": self.session_id, "at": self.clock(),
                                         "items": contributions, "expected_fingerprint": fingerprint(items)})

    def close(self):
        if not self.closed:
            self._prune()
            self._save()
            self.closed = True


def _rebuild(baseline, contributions):
    result = copy.deepcopy(baseline)
    for contribution in sorted(contributions, key=lambda c: (c["at"], c["session"])):
        for iid, evidence in contribution["items"].items():
            current = result.setdefault(iid, {"seconds": 0, "visits": 0, "updates": 0, "activity": {}})
            first = current.get("first_seen")
            current.update(copy.deepcopy(evidence["metadata"]))
            if first:
                current["first_seen"] = min(first, current["first_seen"])
            for key, value in evidence["delta"].items():
                current[key] = current.get(key, 0) + value
            for kind, value in evidence["activity"].items():
                act = current["activity"].setdefault(kind, {"seconds": 0, "text": []})
                act["seconds"] += value["seconds"]
                if value["count"]:
                    act["count"] = act.get("count", 0) + value["count"]
                for text in value["text"]:
                    if text in act["text"]:
                        act["text"].remove(text)
                    act["text"].append(text)
                act["text"] = act["text"][-15:]
            for note in evidence["notes"]:
                if note not in current.setdefault("notes", []):
                    current["notes"].append(copy.deepcopy(note))
            for excerpt in evidence["content"].get("excerpts", []):
                for at in sorted({excerpt["first_seen"], excerpt["last_seen"]}):
                    remember_content(current, {"text": excerpt["text"], "source": excerpt["source"], "observed_at": at,
                                               "decision_quotes": excerpt.get("decision_quotes", [])})
    for current in result.values():
        seconds = {kind: value.get("seconds", 0) for kind, value in current.get("activity", {}).items() if value.get("seconds", 0)}
        current["mostly"] = max(seconds, key=seconds.get) if seconds else None
    return result


def plan_session_deletion(session_id, paths):
    _session(session_id)
    data = Path(paths["data_dir"]).resolve()
    root = Path(paths["memory_dir"]).resolve()
    if not root.is_relative_to(data):
        raise ValueError("memory directory must be inside data directory")
    blockers = []
    if (root / ".deletion.json").exists():
        return {"session": session_id, "blockers": ["Pending deletion must be recovered before planning another deletion."], "files": []}
    pidfile = Path(paths["pidfile"])
    if pidfile.exists():
        try:
            os.kill(int(pidfile.read_text().strip()), 0)
            blockers.append("Stop the tracker before deleting any session.")
        except ProcessLookupError:
            pass
        except (OSError, ValueError):
            blockers.append("Cannot verify tracker is stopped.")
    base_path = root / "contributions" / "baseline.json"
    source = root / "contributions" / (session_id + ".json")
    if not base_path.exists() or not source.exists():
        blockers.append("Session has no reconstructable provenance; legacy deletion is unavailable.")
    if blockers:
        return {"session": session_id, "blockers": blockers, "files": []}
    all_sources = [read_json(p) for p in (root / "contributions").glob("*.json") if p.name != "baseline.json"]
    latest = max(all_sources, key=lambda c: (c["at"], c["session"]))
    index = root / ".index.json"
    if index.exists() and fingerprint({i["id"]: i for i in read_json(index)["items"]}) != latest.get("expected_fingerprint", fingerprint(latest.get("expected_items", {}))):
        blockers.append("Memory changed outside recorded provenance; reconstruction would lose evidence.")
    for replay in (data / "replays").rglob("*.json") if (data / "replays").exists() else []:
        doc = read_json(replay)
        if doc.get("session") == session_id:
            blockers.append(f"Replay evidence still references this session: {replay}")
    retained = [c for c in all_sources if c["session"] != session_id]
    items = _rebuild(read_json(base_path)["items"], retained)
    files = [source, root / "inputs" / (session_id + ".json"), root / "sessions" / (session_id + ".json")]
    owned_frames = []
    for meta_path in data.glob("*.json"):
        meta = read_json(meta_path)
        if meta.get("session") == session_id:
            owned_frames.append(meta_path)
            image = data / (meta.get("image") or "")
            if image.parent.resolve() != data or not image.name.endswith(".jpg"):
                blockers.append("Invalid screenshot path in session metadata.")
            else:
                owned_frames.append(image)
    deleted_images = {p.name for p in owned_frames if p.suffix == ".jpg"}
    for current in items.values():
        if current.get("screenshot") in deleted_images:
            blockers.append("Retained evidence still uses a source screenshot owned by this session; deletion is blocked.")
    files.extend(owned_frames)
    files.extend((root / "inputs" / "frames" / session_id).glob("*.jpg"))
    return {"session": session_id, "blockers": blockers, "files": [str(p) for p in files],
            "items": items, "root": str(root), "data": str(data),
            "retained_latest": max(retained, key=lambda c: (c["at"], c["session"]))["session"] if retained else None}


def recover_deletion(root):
    root = Path(root)
    manifest = root / ".deletion.json"
    if not manifest.exists():
        return
    doc = read_json(manifest)
    data = Path(doc["data"]).resolve()
    if not root.resolve().is_relative_to(data) or root.resolve() != Path(doc["root"]).resolve():
        raise ValueError("invalid deletion manifest root")
    for path in doc["files"]:
        if not Path(path).resolve().is_relative_to(data):
            raise ValueError("invalid deletion manifest path")
    import store
    import notes
    semantic_path = root / "semantic.sqlite3"
    if semantic_path.exists():
        if semantic_path.is_symlink() or not semantic_path.resolve().is_relative_to(root.resolve()):
            raise ValueError("invalid semantic store path")
        from semantic_memory.store import SemanticStore
        from semantic_memory.retention import delete_session as delete_semantic_session
        semantic = SemanticStore(semantic_path)
        try:
            delete_semantic_session(semantic, doc["session"])
        finally:
            semantic.close()
    items = sorted(doc["items"].values(), key=lambda i: i["last_seen"], reverse=True)
    private_write(root / ".index.json", {"schema_version": 2, "items": items})
    private_write(root / "memory.json", {"schema_version": 2, "things": [store.readable(i) for i in items], "updated": _now()})
    private_write(root / "pending.json", notes.pending_view(doc["items"]))
    for source in (root / "contributions").glob("*.json"):
        if source.name == "baseline.json" or source.stem == doc["session"]:
            continue
        contribution = read_json(source)
        old_snapshot = contribution.pop("expected_items", None)
        if old_snapshot is not None:
            contribution["expected_fingerprint"] = fingerprint(old_snapshot)
        if source.stem == doc.get("retained_latest"):
            contribution["expected_fingerprint"] = fingerprint(doc["items"])
        private_write(source, contribution)
    for path in doc["files"]:
        Path(path).unlink(missing_ok=True)
    manifest.unlink()


def delete_session(session_id, paths):
    recover_deletion(paths["memory_dir"])
    plan = plan_session_deletion(session_id, paths)
    if plan["blockers"]:
        raise ValueError("; ".join(plan["blockers"]))
    private_write(Path(plan["root"]) / ".deletion.json", plan)
    recover_deletion(plan["root"])
    return {"session": session_id, "deleted_files": len(plan["files"])}
