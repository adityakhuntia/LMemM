"""Versioned SQLite evidence with explicit ownership and serialized writes."""
import dataclasses
import hashlib
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from .contracts import IngestResult
from .policy import canonical_identity, canonical_path, origin, identifier, validate_source

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE projects(id TEXT PRIMARY KEY,locator TEXT NOT NULL);
CREATE TABLE artifacts(id TEXT PRIMARY KEY,locator TEXT NOT NULL,project_id TEXT REFERENCES projects(id));
CREATE TABLE sources(id TEXT PRIMARY KEY,digest TEXT NOT NULL,at TEXT NOT NULL,session_id TEXT NOT NULL,app_id TEXT NOT NULL,origin TEXT,
 artifact_id TEXT REFERENCES artifacts(id),project_id TEXT REFERENCES projects(id),origin_type TEXT NOT NULL,revision INTEGER NOT NULL,pinned INTEGER NOT NULL DEFAULT 0);
CREATE TABLE blobs(id TEXT PRIMARY KEY,text TEXT NOT NULL,normalized_hash TEXT NOT NULL);
CREATE TABLE occurrences(id TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
 blob_id TEXT NOT NULL REFERENCES blobs(id),span_id TEXT NOT NULL,truncated INTEGER NOT NULL,UNIQUE(source_id,span_id));
CREATE VIRTUAL TABLE evidence_search USING fts5(blob_id UNINDEXED,text);
CREATE TABLE episodes(id TEXT PRIMARY KEY,artifact_id TEXT,started TEXT NOT NULL,ended TEXT NOT NULL,status TEXT NOT NULL,revision INTEGER NOT NULL,reason TEXT,truncated INTEGER NOT NULL DEFAULT 0);
CREATE TABLE episode_evidence(episode_id TEXT REFERENCES episodes(id) ON DELETE CASCADE,occurrence_id TEXT REFERENCES occurrences(id) ON DELETE CASCADE,PRIMARY KEY(episode_id,occurrence_id));
CREATE TABLE claims(id TEXT PRIMARY KEY,episode_id TEXT REFERENCES episodes(id) ON DELETE CASCADE,project_id TEXT,kind TEXT NOT NULL,statement TEXT NOT NULL,status TEXT NOT NULL,task_state TEXT,at TEXT NOT NULL,reason TEXT);
CREATE TABLE edges(id TEXT PRIMARY KEY,subject_id TEXT NOT NULL,object_id TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,method TEXT NOT NULL,first_at TEXT NOT NULL,last_at TEXT NOT NULL);
CREATE TABLE support(id TEXT PRIMARY KEY,entity_id TEXT NOT NULL,occurrence_id TEXT NOT NULL REFERENCES occurrences(id) ON DELETE CASCADE,episode_id TEXT,method TEXT NOT NULL);
CREATE TABLE corrections(id TEXT PRIMARY KEY,action TEXT NOT NULL,subject_id TEXT NOT NULL,object_id TEXT,at TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE jobs(episode_id TEXT PRIMARY KEY REFERENCES episodes(id) ON DELETE CASCADE,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,bytes INTEGER NOT NULL DEFAULT 0,error TEXT);
CREATE TABLE tombstones(source_id TEXT PRIMARY KEY);
"""
class SemanticStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.fchmod(fd, 0o600)
        os.close(fd)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.connection.close()
            raise ValueError("Unsupported semantic schema")
        if version == 0:
            if self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                self.connection.close()
                raise ValueError("Unversioned semantic database")
            self.connection.executescript(SCHEMA)
            self.connection.execute("PRAGMA user_version=1")
            self.connection.commit()
        self.connection.execute("PRAGMA journal_mode=DELETE")
        self.connection.execute("PRAGMA secure_delete=ON")

    @contextmanager
    def transaction(self):
        with self.lock:
            try:
                self.connection.execute("BEGIN IMMEDIATE")
                yield self.connection
                self.connection.commit()
            except BaseException:
                self.connection.rollback()
                raise

    def close(self):
        self.connection.close()

    def count(self, table):
        if table not in {"sources", "occurrences", "blobs", "projects", "artifacts", "episodes", "claims", "edges"}:
            raise ValueError("Unknown count")
        return self.connection.execute("SELECT count(*) FROM " + table).fetchone()[0]

    def ingest(self, envelope, policy):
        # Hash the original envelope to reject changed replays even beyond truncation.
        digest = hashlib.sha256(json.dumps(dataclasses.asdict(envelope), sort_keys=True).encode()).hexdigest()
        s = validate_source(envelope, policy)
        paused = self.connection.execute("SELECT value FROM meta WHERE key='paused'").fetchone()
        if paused and paused[0]:
            raise RuntimeError("Semantic ingestion paused: " + paused[0])
        from .retention import semantic_bytes
        limit = self.connection.execute("SELECT value FROM meta WHERE key='semantic_limit'").fetchone()
        budget = int(limit[0]) if limit else 250 * 1024 * 1024
        projected = 65536 + 4 * sum(len(p.text.encode()) for p in s.spans)
        if semantic_bytes(self) + projected > budget:
            raise RuntimeError("Semantic ingestion paused: projected budget")
        project, artifact = canonical_identity(s)
        ids = tuple(identifier("evidence", s.source_id + "|" + p.span_id) for p in s.spans)
        with self.transaction() as c:
            if c.execute("SELECT 1 FROM tombstones WHERE source_id=?", (s.source_id,)).fetchone():
                raise ValueError("Source was deleted")
            revision = c.execute("SELECT value FROM meta WHERE key='revision'").fetchone()
            if revision and int(revision[0]) != policy.revision:
                raise ValueError("Stale policy")
            c.execute("INSERT OR IGNORE INTO meta VALUES('revision',?)", (str(policy.revision),))
            prior = c.execute("SELECT digest FROM sources WHERE id=?", (s.source_id,)).fetchone()
            if prior:
                if prior[0] != digest:
                    raise ValueError("Conflicting source replay")
                return IngestResult(s.source_id, ids, project, artifact, False)
            if project:
                c.execute("INSERT OR IGNORE INTO projects VALUES(?,?)", (project, canonical_path(s.workspace_locator)))
            browser = s.artifact_locator.startswith(("http://", "https://"))
            if artifact:
                from .policy import canonical_url
                locator = canonical_url(s.artifact_locator) if browser else canonical_path(s.artifact_locator)
                c.execute("INSERT OR IGNORE INTO artifacts VALUES(?,?,?)", (artifact, locator, project))
            c.execute("INSERT INTO sources(id,digest,at,session_id,app_id,origin,artifact_id,project_id,origin_type,revision) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (s.source_id,digest,s.at,s.session_id,s.app_id,origin(s.artifact_locator) if browser else None,artifact,project,s.origin_type,s.policy_revision))
            for oid, span in zip(ids, s.spans):
                blob = identifier("blob", span.text)
                normal = identifier("normal", " ".join(span.text.split()))
                if not c.execute("SELECT 1 FROM blobs WHERE id=?", (blob,)).fetchone():
                    c.execute("INSERT INTO blobs VALUES(?,?,?)", (blob, span.text, normal))
                    c.execute("INSERT INTO evidence_search VALUES(?,?)", (blob, span.text))
                c.execute("INSERT INTO occurrences VALUES(?,?,?,?,?)", (oid,s.source_id,blob,span.span_id,int(span.truncated)))
        return IngestResult(s.source_id, ids, project, artifact, True)

    def evidence(self, ids):
        result = []
        for oid in ids:
            row = self.connection.execute("SELECT o.id,o.source_id,o.truncated,b.text,s.* FROM occurrences o JOIN blobs b ON o.blob_id=b.id JOIN sources s ON o.source_id=s.id WHERE o.id=?", (oid,)).fetchone()
            if row:
                result.append(dict(row))
        return result
