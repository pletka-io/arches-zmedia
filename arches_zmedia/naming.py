"""File names for Arches uploads on zmedia.

zmedia/<spec>/<file>   on zmedia, spec = the tile's graph slug
uploadedfiles/<file>   legacy or tile-less; spec looked up per name
"""

import os
from django.core.exceptions import ObjectDoesNotExist

PREFIX = "zmedia/"
LEGACY_DIR = "uploadedfiles/"
UNLINKED = "unlinked"  # spec for files whose row hangs on no tile


def generate_filename(instance, filename):
    """FILENAME_GENERATOR: a File on a tile goes to zmedia under its graph slug."""
    try:
        spec = instance.tile.resourceinstance.graph.slug
    except (AttributeError, ObjectDoesNotExist):
        spec = None
    name = os.path.basename(filename)
    return f"{PREFIX}{spec}/{name}" if spec else f"{LEGACY_DIR}{name}"


def zmedia_key(name):
    """(spec, file) for a zmedia name, else None."""
    if not name.startswith(PREFIX):
        return None
    spec, _, rel = name[len(PREFIX) :].partition("/")
    return (spec, rel) if spec and rel else None


# ponytail: per-process, slugs only (a file without a row or tile may get one
# any moment); a graph slug rename needs a pod restart
_found = {}


def legacy_spec(name):
    """Graph slug of the File row named `name`, UNLINKED without a tile, None without a row."""
    if name in _found:
        return _found[name]
    from arches.app.models.models import File

    rows = list(
        File.objects.filter(path=name).values_list("tile__resourceinstance__graph__slug", flat=True)[:1]
    )
    if not rows:
        return None
    if not rows[0]:
        return UNLINKED
    _found[name] = rows[0]
    return rows[0]
