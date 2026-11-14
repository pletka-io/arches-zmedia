"""zmedia_link's pure part (spec §2): match Digital Objects to zmedia files and write
loader JSONL that gives each matched one an `image` tile."""
import json
import uuid
from collections import namedtuple

# has_image: an image tile zmedia_link did not write; has_ours: the tile it did write
Do = namedtuple("Do", "resourceid identifier names has_image has_ours", defaults=(False,))
IMAGE_RENDERER = "5e05aa2e-5db0-4922-8938-b4d2b7919733"


def read_inventory(lines):
    rows = {}
    for raw in lines:
        raw = raw.strip()
        if raw:
            row = json.loads(raw)
            rows[row["rel"]] = row
    return rows


def _expected(do, pattern, inventory):
    """The rel for the first name value whose file is in the inventory; else the first usable one."""
    names = (do.names,) if isinstance(do.names, str) else do.names or ()
    names = [n for n in names if n]
    if not names:
        return None, "empty name"
    usable = [n for n in names if "/" not in n]
    if not usable:
        return None, "name with a slash"
    try:
        n = int(do.identifier)
    except (TypeError, ValueError):
        return None, "identifier not a number"
    rels = [pattern.format(identifier=n, name=name) for name in usable]
    return next((r for r in rels if r in inventory), rels[0]), None


def image_tileid(resourceid):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"zmedia-image:{resourceid}"))


def file_id(org, spec, rel):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"zmedia:{org}/{spec}/{rel}"))


def _json(value):
    """Django has psycopg return json/jsonb columns as str; accept that or the parsed value."""
    return json.loads(value) if isinstance(value, str) else value


def _is_our_value(value, org, spec):
    """Every file in the image node is one zmedia_link would write (a UI edit adds or changes one)."""
    prefix = f"zmedia/{spec}/"
    value = _json(value)
    for f in value or []:
        path = f.get("path") if isinstance(f, dict) else None
        if not path or not path.startswith(prefix) or f.get("file_id") != file_id(org, spec, path[len(prefix):]):
            return False
    return True


def has_foreign_image(resourceid, tiles, org, spec):
    """True when the resource has an image tile zmedia_link did not write, or our tile was
    edited since. tiles: {tileid: the image node's value in that tile}."""
    ours = image_tileid(resourceid)
    return any(t != ours or not _is_our_value(v, org, spec) for t, v in (_json(tiles) or {}).items())


def has_our_tile(resourceid, tiles):
    return image_tileid(resourceid) in (_json(tiles) or {})


def match(dos, inventory, pattern, partial=False):
    """partial: the inventory holds only changed rows, so a missing file is not a finding."""
    unmatched, wanted, broken = [], {}, set()
    for do in dos:
        rel, reason = _expected(do, pattern, inventory)
        if partial and not reason and rel not in inventory:
            continue
        if do.has_image:
            unmatched.append(("do", do.resourceid, "has an image already"))
        elif reason:
            unmatched.append(("do", do.resourceid, reason))
        elif rel not in inventory:
            unmatched.append(("do", do.resourceid, "file not found"))
        elif inventory[rel]["status"] == "broken":
            unmatched.append(("do", do.resourceid, "file broken"))
            broken.add(rel)
        elif inventory[rel]["status"] == "deleted" and not do.has_ours:
            unmatched.append(("do", do.resourceid, "file deleted"))
        else:  # a deleted file with our tile: the pair writes an empty tile to clear it
            wanted.setdefault(rel, []).append(do)
    pairs = []
    for rel, group in wanted.items():
        if len(group) > 1:
            unmatched += [("do", d.resourceid, f"duplicate: {rel}") for d in group]
        else:
            pairs.append((group[0], inventory[rel]))
    used = set(wanted) | broken
    unmatched += [("file", rel, "no digital object") for rel, row in inventory.items() if rel not in used and row["status"] != "deleted"]
    return pairs, sorted(unmatched)


def file_value(org, spec, row):
    rel = row["rel"]
    fid = file_id(org, spec, rel)
    return {
        "file_id": fid, "name": rel, "path": f"zmedia/{spec}/{rel}", "url": f"/files/{fid}",
        "size": row["size"], "type": row["mime"], "status": "uploaded", "accepted": True,
        "renderer": IMAGE_RENDERER,
    }


def image_line(do, graphid, nodegroupid, nodeid, value):
    """One loader JSONL line: the resource with only its image tile (load with delta_sync('tile'))."""
    tileid = image_tileid(do.resourceid)
    return json.dumps({
        "resourceInstanceID": do.resourceid, "graphID": graphid,
        "tiles": [{"tileid": tileid, "nodegroup_id": nodegroupid, "parenttile_id": None, "sortorder": 0,
                   "data": {nodeid: [value] if value else []}}],
    }, sort_keys=True)
