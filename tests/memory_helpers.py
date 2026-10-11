"""Synthetic evidence for hybrid-memory tests; never reads user activity."""
from pathlib import Path
from semantic_memory.contracts import AccessPolicy, SourceEnvelope, TextSpan
from semantic_memory.store import SemanticStore

APP = 'com.microsoft.VSCode'
AT = '2026-10-10T10:00:00+00:00'


def make_memory_fixture(tmp_path, project_count=2):
    store = SemanticStore(Path(tmp_path) / 'memory.sqlite3')
    roots = tuple(str(Path(tmp_path) / str(i) / 'repo') for i in range(project_count))
    return store, roots, AccessPolicy(1, frozenset({APP}), frozenset())


def memory_source(sid, root, text, *, at=AT, app=APP, origin_type='observed_screen_text'):
    return SourceEnvelope(sid, at, 'synthetic-session', app, root + '/main.py', root,
                          True, origin_type, (TextSpan('visible', text),), 1)
