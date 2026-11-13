"""Settings for one instance: `globals().update(settings("<slug>"))` in settings.py.

Storage switches to zmedia only where archesctl made the instance's key, so
a dev checkout keeps its files on disk.
"""

import os


def settings(org, etc="/etc/arches"):
    key = f"{etc}/{org}/zmedia_ed25519"
    out = {
        "ZMEDIA": {
            "ORG": org,
            "BASE_URL": "https://media.delving.org",
            "SIZE": 1000,  # zmedia's max_size; deepzoom serves more
            "SFTP_HOST": "upload.media.delving.org",
            "SFTP_PORT": 2222,
            "KEY_FILE": key,
            "KNOWN_HOSTS": f"{etc}/{org}/zmedia_known_hosts",
        }
    }
    if os.path.isfile(key):
        out["FILENAME_GENERATOR"] = "arches_zmedia.naming.generate_filename"
        # settings_local (archesctl) swaps staticfiles for whitenoise and keeps this default
        out["STORAGES"] = {
            "default": {"BACKEND": "arches_zmedia.storage.ZmediaStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
    return out
