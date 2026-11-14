"""Default storage for Arches on zmedia; names outside zmedia stay on local disk."""

import posixpath
from urllib.parse import quote

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible

from . import naming, sftp


def remote_path(cfg, spec, rel):
    return f"/{cfg['ORG']}/{spec}/{rel}"


@deconstructible
class ZmediaStorage(FileSystemStorage):
    def __init__(self, resolve=None, connect=None, **kwargs):
        super().__init__(**kwargs)
        self._resolve = resolve or naming.legacy_spec
        self._connect = connect or sftp.connect

    def _key(self, name):
        """(spec, file) when the file is on zmedia, else None."""
        key = naming.zmedia_key(name)
        if key is None and name.startswith(naming.LEGACY_DIR):
            spec = self._resolve(name)
            if spec:
                key = (spec, name[len(naming.LEGACY_DIR) :])
        return key

    def url(self, name):
        key = self._key(name)
        if key is None:
            return super().url(name)
        cfg = settings.ZMEDIA
        spec, rel = key
        return f"{cfg['BASE_URL']}/thumbnail/{cfg['ORG']}/{spec}/{quote(rel, safe='')}/{cfg.get('SIZE', 1000)}"

    def derivative_url(self, name, kind, size=None):
        """A zmedia derivative of a zmedia-held file (spec §4). Legacy local files have none."""
        key = naming.zmedia_key(name)
        if key is None:
            raise ValueError(f"not on zmedia: {name}")
        spec, rel = key
        cfg = settings.ZMEDIA
        if kind == "thumbnail":
            if size is None:
                raise ValueError("a thumbnail needs a size")
            return f"{cfg['BASE_URL']}/thumbnail/{cfg['ORG']}/{spec}/{quote(rel, safe='')}/{int(size)}"
        if kind == "iiif":
            # zmedia's IIIF identifier is org~spec~id; a `~` inside the id must not read as a separator
            ident = quote(rel, safe="").replace("~", "%7E")
            return f"{cfg['BASE_URL']}/iiif/3/{cfg['ORG']}~{spec}~{ident}"
        raise ValueError(f"unknown derivative: {kind}")

    def _save(self, name, content):
        key = naming.zmedia_key(name)
        if key is None:
            return super()._save(name, content)
        remote = remote_path(settings.ZMEDIA, *key)
        with self._connect(settings.ZMEDIA) as s:
            sftp.ensure_dir(s, posixpath.dirname(remote))
            content.seek(0)
            s.putfo(content, remote)
        return name

    def exists(self, name):
        key = naming.zmedia_key(name)
        if key is None:
            return super().exists(name)
        with self._connect(settings.ZMEDIA) as s:
            try:
                s.stat(remote_path(settings.ZMEDIA, *key))
                return True
            except FileNotFoundError:
                return False

    def size(self, name):
        key = naming.zmedia_key(name)
        if key is None:
            return super().size(name)
        with self._connect(settings.ZMEDIA) as s:
            return s.stat(remote_path(settings.ZMEDIA, *key)).st_size

    def delete(self, name):
        if naming.zmedia_key(name) is None:
            super().delete(name)
        # zmedia originals are kept (dataset spec: arches-files retention keep)
