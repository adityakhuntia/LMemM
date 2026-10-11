"""Server-owned grants; project and source scope are both required."""
import json
import secrets
from .api_contracts import Grant, RequestContext, valid_id
from .contracts import SourceScope


def revision(connection):
    return int(connection.execute("SELECT value FROM meta WHERE key='memory_revision'").fetchone()[0])


def bump_revision(connection):
    value = revision(connection) + 1
    connection.execute("UPDATE meta SET value=? WHERE key='memory_revision'",(str(value),))
    return value


def _decode(row):
    return Grant(row['id'],row['client_id'],frozenset(json.loads(row['project_ids'])),
                 SourceScope(frozenset(json.loads(row['app_ids'])),frozenset(json.loads(row['origins']))),row['revision'],bool(row['revoked']))


def enroll_grant(store, client_id, project_ids, source_scope):
    valid_id(client_id)
    pids = frozenset(project_ids)
    if not pids or len(pids)>64 or not source_scope.app_ids or len(source_scope.app_ids)>64:
        raise ValueError('Invalid scope')
    for value in pids | source_scope.app_ids:
        valid_id(value)
    with store.transaction() as c:
        for pid in pids:
            if not c.execute('SELECT 1 FROM project_bindings WHERE project_id=? AND active=1',(pid,)).fetchone():
                raise ValueError('unavailable')
        grant = Grant('grant-'+secrets.token_hex(16),client_id,pids,source_scope,revision(c),False)
        c.execute('INSERT INTO memory_grants VALUES(?,?,?,?,?,?,0)',(grant.id,client_id,json.dumps(sorted(pids)),json.dumps(sorted(source_scope.app_ids)),json.dumps(sorted(source_scope.origins)),grant.revision))
    return grant


def current_grant(store, ctx, project_id):
    with store.lock:
        c=store.connection
        row=c.execute('SELECT * FROM memory_grants WHERE id=? AND revoked=0',(ctx.grant_id,)).fetchone()
        if not row or ctx.policy_revision != revision(c):
            raise ValueError('unavailable')
        grant=_decode(row)
        if project_id not in grant.project_ids or not c.execute('SELECT 1 FROM project_bindings WHERE project_id=? AND active=1',(project_id,)).fetchone():
            raise ValueError('unavailable')
        return grant


def authorize(store, grant_id, project_id):
    with store.lock:
        ctx=RequestContext(grant_id,revision(store.connection))
        current_grant(store,ctx,project_id)
        return ctx


def revoke_grant(store, grant_id):
    with store.transaction() as c:
        if not c.execute('UPDATE memory_grants SET revoked=1 WHERE id=?',(grant_id,)).rowcount:
            raise ValueError('unavailable')
        return bump_revision(c)


def revoke_project(store,project_id):
    """Disable semantic access; ordinary UI archive never calls this operation."""
    with store.transaction() as c:
        if not c.execute('UPDATE project_bindings SET active=0 WHERE project_id=?',(project_id,)).rowcount:
            raise ValueError('unavailable')
        for row in c.execute('SELECT id,project_ids FROM memory_grants WHERE revoked=0').fetchall():
            if project_id in json.loads(row['project_ids']):c.execute('UPDATE memory_grants SET revoked=1 WHERE id=?',(row['id'],))
        c.execute("UPDATE index_jobs SET state='cancelled',error='Project revoked' WHERE source_id IN (SELECT id FROM sources WHERE project_id=?)",(project_id,))
        return bump_revision(c)
