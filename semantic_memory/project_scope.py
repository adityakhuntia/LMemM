"""Stable UI-project enrollment by canonical workspace root, never title."""
from pathlib import Path
from .api_contracts import ProjectBinding, valid_id
from .policy import identifier, utc


def _binding(row):
    return ProjectBinding(row['ui_project_id'],row['project_id'],row['workspace_root'],row['enrolled_at'],bool(row['active'])) if row else None


def bind_project(store, ui_project_id, root, at):
    valid_id(ui_project_id)
    if not isinstance(root,str) or not root.startswith('/') or '\x00' in root:
        raise ValueError('Absolute workspace root required')
    root = str(Path(root).resolve())
    if root == '/' or len(root.encode()) > 4096:
        raise ValueError('Invalid workspace root')
    at = utc(at)
    pid = identifier('project', root)
    with store.transaction() as c:
        prior = c.execute('SELECT * FROM project_bindings WHERE ui_project_id=? OR project_id=?', (ui_project_id,pid)).fetchone()
        if prior:
            if prior['ui_project_id'] != ui_project_id or prior['project_id'] != pid:
                raise ValueError('Project is already linked')
            return _binding(prior)
        c.execute('INSERT OR IGNORE INTO projects VALUES(?,?)',(pid,root))
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
