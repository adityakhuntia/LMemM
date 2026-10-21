"""Stable UI-project enrollment by canonical workspace root, never title."""
from pathlib import Path
from .api_contracts import ProjectBinding, valid_id
from .policy import identifier, utc


def _binding(row):
    return ProjectBinding(row['ui_project_id'],row['project_id'],row['workspace_root'],row['enrolled_at'],bool(row['active'])) if row else None


def bind_project(store, ui_project_id, root, at):
    valid_id(ui_project_id)
    if root is not None:
        if not isinstance(root,str) or not root.startswith('/') or '\x00' in root:
            raise ValueError('Absolute workspace root required')
        root = str(Path(root).resolve())
        if root == '/' or len(root.encode()) > 4096:
            raise ValueError('Invalid workspace root')
    at = utc(at)
    pid = identifier('project', root) if root else identifier('project','native:'+ui_project_id)
    with store.transaction() as c:
        prior = c.execute('SELECT * FROM project_bindings WHERE ui_project_id=?', (ui_project_id,)).fetchone()
        occupied = c.execute('SELECT * FROM project_bindings WHERE workspace_root=?', (root,)).fetchone() if root else None
        if occupied and occupied['ui_project_id'] != ui_project_id:
            raise ValueError('Project is already linked')
        if prior:
            if root and prior['workspace_root'] and prior['workspace_root'] != root:
                raise ValueError('Project is already linked')
            if root and prior['workspace_root'] is None:
                c.execute('UPDATE project_bindings SET workspace_root=? WHERE ui_project_id=?',(root,ui_project_id))
                c.execute('UPDATE projects SET locator=? WHERE id=?',(root,prior['project_id']))
                from .grants import bump_revision
                bump_revision(c)
            return resolve_binding(store,ui_project_id)
        c.execute('INSERT OR IGNORE INTO projects VALUES(?,?)',(pid,root or 'lmemm-project:'+ui_project_id))
        c.execute('INSERT INTO project_bindings VALUES(?,?,?,?,1)',(ui_project_id,pid,root,at))
    return resolve_binding(store,ui_project_id)


def resolve_binding(store, ui_project_id):
    with store.lock:
        return _binding(store.connection.execute('SELECT * FROM project_bindings WHERE ui_project_id=?',(ui_project_id,)).fetchone())


def set_binding_active(store, ui_project_id, active):
    with store.transaction() as c:
        if not c.execute('UPDATE project_bindings SET active=? WHERE ui_project_id=?',(int(bool(active)),ui_project_id)).rowcount:
            raise ValueError('unavailable')
        from .grants import bump_revision
        bump_revision(c)
