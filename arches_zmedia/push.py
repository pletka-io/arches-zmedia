import os

from . import naming


def plan_push(rows, remote, local_path):
    """Legacy files zmedia lacks: ([(local, spec, file)], [names missing on disk])."""
    todo, missing, seen = [], [], set()
    for name, spec in rows:
        if not name.startswith(naming.LEGACY_DIR):
            continue
        spec = spec or naming.UNLINKED
        rel = name[len(naming.LEGACY_DIR) :]
        if (spec, rel) in seen or rel in remote.get(spec, set()):
            continue
        seen.add((spec, rel))
        local = local_path(name)
        if os.path.isfile(local):
            todo.append((local, spec, rel))
        else:
            missing.append(name)
    return todo, missing
