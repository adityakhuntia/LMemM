"""Atomic, additive v1→v2 upgrade; no evidence reconstruction or file crawl."""
VERSION = 2
V1_TABLES = {'meta','projects','artifacts','sources','blobs','occurrences','evidence_search',
             'episodes','episode_evidence','claims','edges','support','corrections','jobs','tombstones'}
V2_SQL = (
    'CREATE TABLE project_bindings(ui_project_id TEXT PRIMARY KEY, project_id TEXT NOT NULL UNIQUE REFERENCES projects(id), workspace_root TEXT NOT NULL UNIQUE, enrolled_at TEXT NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1)))',
    'CREATE TABLE memory_grants(id TEXT PRIMARY KEY, client_id TEXT NOT NULL, project_ids TEXT NOT NULL, app_ids TEXT NOT NULL, origins TEXT NOT NULL, revision INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)',
    'CREATE TABLE note_mirrors(note_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), revision TEXT NOT NULL, source_id TEXT REFERENCES sources(id) ON DELETE SET NULL, deleted INTEGER NOT NULL DEFAULT 0)',
    'CREATE TABLE note_fences(project_id TEXT PRIMARY KEY REFERENCES projects(id), mutation_id TEXT NOT NULL)',
    'CREATE TABLE memory_chunks(id TEXT PRIMARY KEY, occurrence_id TEXT NOT NULL REFERENCES occurrences(id) ON DELETE CASCADE, version INTEGER NOT NULL, start_char INTEGER NOT NULL, end_char INTEGER NOT NULL, text TEXT NOT NULL, UNIQUE(occurrence_id,version,start_char,end_char))',
    'CREATE VIRTUAL TABLE chunk_search USING fts5(chunk_id UNINDEXED, text)',
    'CREATE TRIGGER chunk_delete AFTER DELETE ON memory_chunks BEGIN DELETE FROM chunk_search WHERE chunk_id=old.id; END',
    'CREATE TABLE index_generations(id TEXT PRIMARY KEY, manifest TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL)',
    'CREATE TABLE chunk_vectors(chunk_id TEXT REFERENCES memory_chunks(id) ON DELETE CASCADE, generation_id TEXT REFERENCES index_generations(id) ON DELETE CASCADE, vector BLOB NOT NULL, PRIMARY KEY(chunk_id,generation_id))',
    'CREATE TABLE index_jobs(source_id TEXT PRIMARY KEY REFERENCES sources(id) ON DELETE CASCADE, generation_id TEXT REFERENCES index_generations(id) ON DELETE CASCADE, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, error TEXT)',
    'CREATE INDEX source_project_at ON sources(project_id, at)',
    'CREATE INDEX chunk_occurrence ON memory_chunks(occurrence_id)',
    'CREATE INDEX occurrence_source ON occurrences(source_id)',
)
V2_TABLES = {'project_bindings','memory_grants','note_mirrors','note_fences','memory_chunks',
             'chunk_search','index_generations','chunk_vectors','index_jobs'}


def validate_schema(connection, version):
    if version not in (1, VERSION):
        raise ValueError('Unsupported semantic schema')
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = V1_TABLES | (V2_TABLES if version == VERSION else set())
    if not required <= tables:
        raise ValueError('Incomplete semantic schema')
    # Detect falsely versioned databases even when all table names are present.
    for table, columns in {'meta':{'key','value'},'sources':{'id','project_id','revision','origin_type'},
                           'occurrences':{'id','source_id','blob_id','span_id'},'projects':{'id','locator'}}.items():
        if not columns <= {r[1] for r in connection.execute('PRAGMA table_info('+table+')')}:
            raise ValueError('Incomplete semantic schema')


def migrate(connection):
    version = connection.execute('PRAGMA user_version').fetchone()[0]
    validate_schema(connection, version)
    if version == VERSION:
        return
    try:
        connection.execute('BEGIN IMMEDIATE')
        for statement in V2_SQL:
            connection.execute(statement)
        connection.execute("INSERT INTO meta(key,value) VALUES('memory_revision','1')")
        connection.execute('PRAGMA user_version=2')
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
