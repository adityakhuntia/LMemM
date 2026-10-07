"""Immutable ingestion and retrieval boundaries."""
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class TextSpan:
    span_id: str
    text: str
    truncated: bool = False

@dataclass(frozen=True)
class SourceEnvelope:
    source_id: str
    at: str
    session_id: str
    app_id: str
    artifact_locator: str
    workspace_locator: str | None
    identity_authoritative: bool
    origin_type: str
    spans: tuple[TextSpan, ...]
    policy_revision: int
    private_context: bool = False
    browser_context_known: bool = True

@dataclass(frozen=True)
class AccessPolicy:
    revision: int
    allowed_apps: frozenset[str]
    allowed_origins: frozenset[str]
    denied_origins: frozenset[str] = frozenset()

@dataclass(frozen=True)
class SourceScope:
    app_ids: frozenset[str]
    origins: frozenset[str] = frozenset()

@dataclass(frozen=True)
class IngestResult:
    source_id: str
    occurrence_ids: tuple[str, ...]
    project_id: str | None
    artifact_id: str | None
    inserted: bool

@dataclass(frozen=True)
class EpisodeRequest:
    episode_id: str
    evidence: tuple[dict, ...]
    candidates: tuple[dict, ...]
    revision: int
    truncated: bool = False

@dataclass(frozen=True)
class ExtractionResult:
    candidates: tuple[dict, ...]

@dataclass(frozen=True)
class Correction:
    action: str
    subject_id: str
    object_id: str | None
    at: str
    evidence_ids: tuple[str, ...] = ()
    actor: str = "user"

@dataclass(frozen=True)
class JobResult:
    episode_id: str
    status: str
    attempts: int

@dataclass(frozen=True)
class DeletionResult:
    sources: int
    occurrences: int

@dataclass(frozen=True)
class BudgetStatus:
    semantic_bytes: int
    raw_bytes: int
    pruned: int
    paused_reason: str | None

@dataclass(frozen=True)
class ApplyResult:
    claims: int
    edges: int

@dataclass
class ContextPacket:
    project_id: str
    start: str
    end: str
    recent_changes: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    open_tasks: list = field(default_factory=list)
    artifacts: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    unknowns: list = field(default_factory=list)
    citations: dict = field(default_factory=dict)
    coverage: dict = field(default_factory=dict)

