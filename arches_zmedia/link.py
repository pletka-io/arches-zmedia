"""zmedia_link's pure part (spec §2): match Digital Objects to zmedia files and write
loader JSONL that gives each matched one an `image` tile."""
import json
import uuid
from collections import namedtuple

Do = namedtuple("Do", "resourceid identifier name has_image")
IMAGE_RENDERER = "5e05aa2e-5db0-4922-8938-b4d2b7919733"


def read_inventory(lines):
    rows = {}
    for raw in lines:
        raw = raw.strip()
        if raw:
            row = json.loads(raw)
            rows[row["rel"]] = row
    return rows


def _expected(do, pattern):
    if not do.name:
        return None, "empty name"
    if "/" in do.name:
        return None, "name with a slash"
    try:
        n = int(do.identifier)
    except (TypeError, ValueError):
        return None, "identifier not a number"
    return pattern.format(identifier=n, name=do.name), None


def match(dos, inventory, pattern):
    unmatched, wanted = [], {}
    for do in dos:
        if do.has_image:
            unmatched.append(("do", do.resourceid, "has an image already"))
            continue
        rel, reason = _expected(do, pattern)
        if reason:
            unmatched.append(("do", do.resourceid, reason))
        elif rel not in inventory:
            unmatched.append(("do", do.resourceid, "file not found"))
        else:
            wanted.setdefault(rel, []).append(do)
    pairs = []
    for rel, group in wanted.items():
        if len(group) > 1:
            unmatched += [("do", d.resourceid, f"duplicate: {rel}") for d in group]
        else:
            pairs.append((group[0], inventory[rel]))
    used = set(wanted)
    unmatched += [("file", rel, "no digital object") for rel, row in inventory.items() if rel not in used and row["status"] != "deleted"]
    return pairs, sorted(unmatched)


def file_value(org, spec, row):
    rel = row["rel"]
    fid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"zmedia:{org}/{spec}/{rel}"))
    return {
        "file_id": fid, "name": rel, "path": f"zmedia/{spec}/{rel}", "url": f"/files/{fid}",
        "size": row["size"], "type": row["mime"], "status": "uploaded", "accepted": True,
        "renderer": IMAGE_RENDERER,
    }


def image_line(do, graphid, nodegroupid, nodeid, value):
    """One loader JSONL line: the resource with only its image tile (load with delta_sync('tile'))."""
    tileid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"zmedia-image:{do.resourceid}"))
    return json.dumps({
        "resourceInstanceID": do.resourceid, "graphID": graphid,
        "tiles": [{"tileid": tileid, "nodegroup_id": nodegroupid, "parenttile_id": None, "sortorder": 0,
                   "data": {nodeid: [value] if value else []}}],
    }, sort_keys=True)
