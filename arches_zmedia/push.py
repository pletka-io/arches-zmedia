import os

from . import naming


def plan_push(rows, remote, local_path):
    """Legacy files zmedia lacks.

    rows: (name, graph slug or None); remote: {spec: {file: size}}.
    Returns ([(local, spec, file)], [names missing on disk], [names whose
    zmedia file differs in size: another file by that name, or a broken one]).
    """
    todo, missing, conflicts, seen = [], [], [], set()
    for name, spec in rows:
        if not name.startswith(naming.LEGACY_DIR):
            continue
        spec = spec or naming.UNLINKED
        rel = name[len(naming.LEGACY_DIR) :]
        if (spec, rel) in seen:
            continue
        seen.add((spec, rel))
        local = local_path(name)
        if not os.path.isfile(local):
            if rel not in remote.get(spec, {}):
                missing.append(name)
            continue
        size = remote.get(spec, {}).get(rel)
        if size is None:
            todo.append((local, spec, rel))
        elif size != os.path.getsize(local):
            conflicts.append(name)
    return todo, missing, conflicts
