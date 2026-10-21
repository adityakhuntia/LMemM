"""Immutable v1 service boundaries; authorization contexts are server-owned."""
from dataclasses import dataclass
from .contracts import SourceScope
from .policy import utc


def valid_id(value):
    if not isinstance(value, str) or not value or len(value.encode()) > 256 or '\x00' in value:
        raise ValueError('Invalid identifier')
    return value


@dataclass(frozen=True)
class ProjectBinding:
    ui_project_id: str
    project_id: str
    workspace_root: str | None
    enrolled_at: str
    active: bool


@dataclass(frozen=True)
class Grant:
    id: str
    client_id: str
    project_ids: frozenset[str]
    source_scope: SourceScope
    revision: int
    revoked: bool


@dataclass(frozen=True)
class RequestContext:
    grant_id: str
    policy_revision: int


@dataclass(frozen=True)
class Query:
    project_id: str
    text: str
    start: str | None = None
    end: str | None = None
    limit: int = 10

    def __post_init__(self):
        valid_id(self.project_id)
        if not isinstance(self.text, str) or len(self.text.encode()) > 2048 or '\x00' in self.text:
            raise ValueError('Invalid query')
        if type(self.limit) is not int or not 1 <= self.limit <= 10:
            raise ValueError('Invalid limit')
        for key in ('start', 'end'):
            value = getattr(self, key)
            if value is not None:
                object.__setattr__(self, key, utc(value))
        if self.start and self.end and self.start > self.end:
            raise ValueError('Invalid interval')


@dataclass(frozen=True)
class EvidenceHit:
    chunk_id: str
    citation_id: str
    artifact_id: str
    locator: str
    at: str
    origin_type: str
    text: str
    truncated: bool
    score: float
    related_to: str | None = None


@dataclass(frozen=True)
class SearchResult:
    project_id: str
    policy_revision: int
    primary: tuple[EvidenceHit, ...]
    related: tuple[EvidenceHit, ...]
    coverage: dict
    mode: str
    start: str | None = None
    end: str | None = None


@dataclass(frozen=True)
class ContextResult:
    project_id: str
    policy_revision: int
    start: str
    end: str
    decisions: tuple
    open_tasks: tuple
    recent_evidence: tuple
    unknowns: tuple
    citations: dict
    coverage: dict


@dataclass(frozen=True)
class SourceDetail:
    project_id: str
    citation_id: str
    text: str
    locator: str
    at: str
    origin_type: str
    truncated: bool
    can_open_file: bool
    title: str = ''
    url: str | None = None
    source_id: str | None = None


@dataclass(frozen=True)
class MemoryStatus:
    state: str
    reason: str | None
    indexed_at: str | None
    enrolled_at: str | None
    pending: int
    failed: int
    model_state: str
    retained_start: str | None
    bytes_used: int


@dataclass(frozen=True)
class ModelManifest:
    model_id: str
    digest: str
    dimension: int
    max_input_tokens: int
    chunk_version: int
    runtime: str
    weights_path: str


@dataclass(frozen=True)
class NoteSnapshot:
    note_id: str
    revision: str
    project_id: str
    text: str
    created_at: str
    done_at: str | None
    deleted: bool
    origin: str


@dataclass(frozen=True)
class SyncResult:
    applied: int
    pending: int
    rejected: int
