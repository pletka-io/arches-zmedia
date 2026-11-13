# arches-zmedia

Arches uploads on zmedia. A file uploaded onto a tile is named
`zmedia/<graph slug>/<file>` and stored over SFTP at `/<org>/<spec>/<file>`
(account `media-<org>`); its URL is zmedia's thumbnail route. Legacy names
`uploadedfiles/<file>` find their spec through file → tile → graph. Other
names (ETL temp files, exports) stay on local disk.

In the project's `settings.py`:

    from arches_zmedia.conf import settings as zmedia_settings
    globals().update(zmedia_settings("<slug>"))
    INSTALLED_APPS += ("arches_zmedia",)

`zmedia_settings` always sets `ZMEDIA`; it switches `FILENAME_GENERATOR`
and `STORAGES["default"]` to zmedia only when the instance's key
`/etc/arches/<slug>/zmedia_ed25519` exists (made by `archesctl key <slug>`),
so a dev checkout keeps files on disk.

`python manage.py zmedia_push [--dry-run]` uploads legacy files zmedia lacks.
Deleting a file in Arches keeps the original on zmedia.

## Linking existing files

    python manage.py zmedia_link <spec> --pattern "{identifier:06d}_{name}" \
        --identifier-node <alias> --name-node <alias> --image-node <alias> \
        --out <dir> [--since <cursor>]

Matches each Digital Object of graph `<spec>` to a file in the zmedia inventory
(file name from `--pattern`, filled with the object's identifier and name) and
writes `link.jsonl` (one image tile per match), `unmatched.tsv` and `cursor`
to `<dir>`. Load `link.jsonl` with `delta_sync('tile')`; tile mode never
deletes tiles. Pass the saved cursor as `--since` for an incremental run.
