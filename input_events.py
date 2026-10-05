"""Bounded interaction summaries. This module never receives characters/keycodes."""

from datetime import datetime, timedelta


REGIONS = {f"{y}-{x}" for y in ("top", "middle", "bottom") for x in ("left", "center", "right")} | {"center", "unknown"}
KINDS = {"key": set(), "move": {"region"}, "drag": {"region"},
         "click": {"region", "button"}, "scroll": {"direction", "magnitude"}}


class Aggregator:
    def __init__(self, session_id, anchor_utc, origin_ns, transient_seconds=30, max_summaries=256):
        if not 0 < transient_seconds <= 30 or max_summaries < 2:
            raise ValueError("invalid interaction buffer limits")
        self.session_id = session_id
        self.anchor = datetime.fromisoformat(anchor_utc)
        if self.anchor.tzinfo is None:
            raise ValueError("UTC anchor must include timezone")
        self.origin_ns = origin_ns
        self.ttl_ns = int(transient_seconds * 1e9)
        self.max_summaries = max_summaries
        self.last_ns = origin_ns
        self.context_id = None
        self.pending = {}
        self.ready = []
        self.sequence = 0

    def _record(self, kind, start, end, payload, context_id=None):
        self.sequence += 1
        def utc(ns):
            return (self.anchor + timedelta(microseconds=(ns - self.origin_ns) / 1000)).isoformat()
        event = {"event_id": f"{self.session_id}:{self.sequence}", "sequence": self.sequence,
                 "kind": kind, "context_id": context_id, "start_offset_ns": start - self.origin_ns,
                 "end_offset_ns": end - self.origin_ns, "start_utc": utc(start), "end_utc": utc(end),
                 "payload": dict(payload)}
        if len(self.ready) >= self.max_summaries:
            self.ready.clear()
            self.pending.clear()
            event.update(kind="gap", context_id=None, payload={"reason": "overflow"})
        self.ready.append(event)

    def clear(self, reason):
        self.pending.clear()
        self.ready.clear()
        self.context_id = None
        self._record("gap", self.last_ns, self.last_ns, {"reason": reason})

    def _flush(self, key):
        burst = self.pending.pop(key)
        self._record(key, burst["start"], burst["end"], burst["payload"], burst["context"])

    def feed(self, kind, event_ns, context, payload):
        if kind not in KINDS or set(payload) != KINDS[kind]:
            raise ValueError("unsupported input payload")
        if not isinstance(event_ns, int) or isinstance(event_ns, bool):
            raise ValueError("event time must be integer nanoseconds")
        if not isinstance(context.get("id"), str) or not context["id"]:
            raise ValueError("missing permitted context")
        if "region" in payload and payload["region"] not in REGIONS:
            raise ValueError("invalid coarse region")
        if kind == "click" and payload["button"] not in {"left", "right", "other"}:
            raise ValueError("invalid button category")
        if kind == "scroll" and (payload["direction"] not in {"up", "down", "left", "right", "mixed"}
                                 or payload["magnitude"] not in {"small", "medium", "large"}):
            raise ValueError("invalid scroll category")
        if event_ns < self.last_ns:
            self.clear("out_of_order")
            return
        if self.context_id is not None and self.context_id != context["id"]:
            self.clear("context_change")
        self.context_id = context["id"]
        self.last_ns = event_ns
        for key, burst in list(self.pending.items()):
            threshold = 1_000_000_000 if key == "pointer_movement" else 750_000_000
            if event_ns - burst["end"] >= threshold or key == "pointer_movement" and event_ns - burst["start"] >= threshold:
                self._flush(key)
        if kind == "click":
            self._record("click", event_ns, event_ns, payload, self.context_id)
            return
        key = "keyboard_activity" if kind == "key" else "pointer_movement" if kind in {"move", "drag"} else "scroll"
        if key not in self.pending:
            reduced = {"count": 0} if kind == "key" else {"from": payload["region"], "to": payload["region"], "drag": False} if kind in {"move", "drag"} else dict(payload)
            self.pending[key] = {"start": event_ns, "end": event_ns, "context": self.context_id, "payload": reduced}
        burst = self.pending[key]
        burst["end"] = event_ns
        if kind == "key":
            burst["payload"]["count"] += 1
        elif kind in {"move", "drag"}:
            burst["payload"].update(to=payload["region"], drag=burst["payload"]["drag"] or kind == "drag")
        else:
            if burst["payload"]["direction"] != payload["direction"]:
                burst["payload"]["direction"] = "mixed"
            levels = ["small", "medium", "large"]
            burst["payload"]["magnitude"] = max((burst["payload"]["magnitude"], payload["magnitude"]), key=levels.index)

    def drain(self, now_ns):
        if any(now_ns - b["start"] > self.ttl_ns for b in self.pending.values()) or any(
                now_ns - (e["end_offset_ns"] + self.origin_ns) > self.ttl_ns for e in self.ready):
            self.last_ns = max(self.last_ns, now_ns)
            self.clear("expired")
        for key, burst in list(self.pending.items()):
            wait = 1_000_000_000 if key == "pointer_movement" else 750_000_000
            if now_ns - burst["end"] >= wait or key == "pointer_movement" and now_ns - burst["start"] >= wait:
                self._flush(key)
        result, self.ready = sorted(self.ready, key=lambda e: (e["start_offset_ns"], e["sequence"])), []
        return result
