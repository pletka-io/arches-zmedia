# GAP: Digital Object images, shown on the records they depict

Date: 2026-11-13
Status: draft, for review
Depends on: zmedia inventory API (kakugo spec
`2026-11-13-zmedia-inventory-design.md`): `GET /api/inventory/<org>/<spec>` on
dash, reachable from the Arches host over WireGuard with an app token bound to
the instance's org.

## 1. Goal

GAP describes its photographs as Digital Object resources. Each one names the
file and points at what it shows through `depicts_*` nodes (trench, context,
artefact, finds collection, feature, sample, place). The files are already on
zmedia under `gap/digital_object/`, named `<identifier, 6 digits>_<name>`, but
no Digital Object has a file attached, so no image shows anywhere in GAP.

After this work:

1. Every Digital Object whose file is on zmedia has it in its `image` node,
   as an ordinary Arches File row whose name points at zmedia
   (`zmedia/digital_object/000001_DSC_0284.JPG`). The storage backend from
   v0.1.0 already serves those names.
2. A trench, context, artefact (etc.) report shows a gallery of the images of
   the Digital Objects that depict it, ordered by Digital Object identifier,
   and its header shows the first one when the record has no image of its own.

GAP is the first instance; the same pieces later serve commonground (its
Digital Object graph, then migrating its directly attached files).

Not in this spec: a IIIF manifest per record (next spec: built from the
record's Digital Objects in this same order, with explicit ordering added
then), commonground, restricting uploads to Digital Objects, moving files
between zmedia specs.

## 2. Linking files: `zmedia_link`

A management command in arches-zmedia:

```
manage.py zmedia_link digital_object \
    --pattern "{identifier:06d}_{name}" \
    --identifier-node identifier_content --name-node name_content \
    --image-node image \
    --out <dir> [--since <cursor>]
```

1. Reads `/api/inventory/<org>/digital_object` from dash
   (`ZMEDIA["INVENTORY_URL"]`, set per host in the instance settings;
   `ZMEDIA["ORG"]`; bearer token from `/etc/arches/<slug>/zmedia-inventory.token`,
   read by `conf.settings(org)` like the SFTP key), zstd-encoded (concatenated
   frames), streamed.
2. Reads every Digital Object's identifier and name from the database.
3. Builds the expected file name per Digital Object from `--pattern` and
   matches it against the inventory's `rel`.
4. Writes:
   - `link.jsonl`: one resource per matched Digital Object in the archessql
     JSONL import shape, carrying one `image` tile with one file value
     (below). Only the `image` nodegroup is touched; the loader's delta keeps
     the resource's other tiles as they are.
   - `unmatched.tsv`: Digital Objects with no file (empty name, name not
     found), files with no Digital Object (`.heic` and other leftovers), and
     duplicates (two Digital Objects expecting the same file).
   - `cursor`: the inventory's `X-Zmedia-Cursor`, for the next `--since` run.
5. Prints counts: matched, unmatched each way, duplicates.

The file value in the tile:

```json
{"file_id": "<uuid5(NAMESPACE_URL, 'zmedia:gap/digital_object/000001_DSC_0284.JPG')>",
 "name": "000001_DSC_0284.JPG",
 "path": "zmedia/digital_object/000001_DSC_0284.JPG",
 "url": "/files/<file_id>",
 "size": 5123456, "type": "image/jpeg",
 "status": "uploaded", "accepted": true}
```

The `file_id` is derived from the zmedia path, so a re-run produces the same
tiles and the delta is empty. The exact set of keys follows what Arches 8.1
writes for an uploaded file; the plan copies them from a tile the UI made.

With `--since`, only Digital Objects whose file changed or was deleted are
written. A deleted file clears the `image` tile only where that tile is the
one `zmedia_link` wrote; otherwise it is reported as "file deleted". A broken
file is reported, not linked. An `image` tile someone edited by hand (any value
that is not one `zmedia_link` would write) counts as theirs and is never
overwritten. The gallery and header sort identifiers in natural numeric order
(`natural=true` on the related-resources endpoint).

Errors stop the command before any output is written: inventory `401`/`403`,
an unreadable inventory, a graph without the named nodes.

## 3. The loader writes File rows (archessql, arches-fleet)

Today the loader writes tiles but no `files` rows, and `sync_delta.sql`
deletes the `files` rows of every tile it deletes or replaces
(`internal/archessql/sql/sync/sync_delta.sql:188,293`). A file-list value
written through the loader therefore has no File row, and an uploaded file
loses its row when its resource is reloaded.

Change in `sync_delta.sql`, both paths:

- After the tiles are inserted, upsert one `files` row per file-list value
  that carries `file_id` and `path`:
  `INSERT INTO files(fileid, path, tileid) ... ON CONFLICT (fileid) DO UPDATE
  SET path = EXCLUDED.path, tileid = EXCLUDED.tileid`.
- Delete a `files` row only when its `file_id` no longer occurs in any
  file-list value of the resource's new tiles. A file-list value without
  `path` keeps its existing row as it is.

Run `delta preview` before `delta_sync`. Expected on GAP: about 18k `image`
tiles added on existing Digital Objects, 0 resources deleted.

## 4. Derivatives through the storage backend

zmedia makes every derivative: thumbnails at any size
(`/thumbnail/<org>/<spec>/<rel>/<size>`), deepzoom, and the IIIF Image API
(`/iiif/{2|3}/<org>~<spec>~<rel>/...`, kakugo spec
`2026-10-24-iiif-image-api-design.md` §3.1). Arches does not
(`GENERATE_THUMBNAILS_ON_DEMAND` stays off: turning it on would pull every
original over SFTP to store a PNG in the database).

`ZmediaStorage` names them, so nothing outside the storage knows zmedia's URL
shapes:

```python
storage.url(name)                          # thumbnail at ZMEDIA["SIZE"] (1000), as in v0.1.0
storage.derivative_url(name, "thumbnail", size=300)
storage.derivative_url(name, "iiif")       # IIIF Image API v3 service base, no trailing slash
```

`derivative_url` raises `ValueError` for an unknown kind, and for a name
outside `zmedia/` (a legacy local file has no derivatives).

File values keep Arches' own `url`, `/files/<file_id>`, the same as files
uploaded through the UI. arches-zmedia adds a `FileView` subclass, routed at
`files/<uuid>` ahead of Arches' own (the project adds one URL line). It keeps
Arches' permission checks unchanged and changes only where it redirects:

- `?thumbnail=true` → `derivative_url(name, "thumbnail", ZMEDIA["THUMB_SIZE"])`
  (default 300);
- `?size=<n>` → `derivative_url(name, "thumbnail", n)`, `n` limited to
  `ZMEDIA["SIZES"]` (default 100, 300, 500, 1000) so a caller cannot ask for
  arbitrary sizes;
- no parameter → `storage.url(name)`, as today;
- a file not on zmedia → Arches' own behaviour.

The `iiif` kind has no caller in this spec; the record manifest (next spec)
uses it for each canvas's image service.

## 5. Display (fork pletka-io/arches-modular-reports)

### 5.1 `RelatedImagesSection.vue`

New report component, configured as:

```json
{"component": "arches_modular_reports/ModularReport/components/RelatedImagesSection",
 "config": {"graph_slug": "digital_object", "image_node_alias": "image",
            "sort_field": "identifier_content", "rows_per_page": 24}}
```

- Data comes from the existing `RelatedResourceView`
  (`app/views/modular_report.py:148`), which already reads relations in both
  directions and pages them, with `node_aliases=image,identifier_content`.
  For a file-list node it already returns `links` with `is_file` and `url`
  (`app/utils/nodegroup_tile_data_utils.py:639`). No backend change.
- A grid of thumbnails (`<url>?thumbnail=true`, §4), each linking to its Digital
  Object report, with the Digital Object's name as caption, and a pager.
- A Digital Object without an image is left out of the grid.
- No related Digital Objects: the section is hidden.
- An image that fails to load shows a neutral placeholder.

### 5.2 Header image fallback

`ReportTombstone` gains an optional `related_image` config, the same three
keys (`graph_slug`, `image_node_alias`, `sort_field`). When the record's own
`image_node_alias` has no file, it asks the same view with `rows_per_page=1`
and shows that image.

### 5.3 Release

Version `2.0.0+delving.4`, tag `v2.0.0-delving.4`; GAP's pin moves to it.

## 6. GAP configuration

`gap/management/commands/customize_modular_report_config.py` gains the
section and the header fallback for artefact, context, trench,
finds_collection, feature, sample and place: the existing
`RelatedResourcesSection` for `digital_object` is replaced by
`RelatedImagesSection`, and `related_image` is set on the tombstone. Re-run
with `--force` per graph.

## 7. Testing and acceptance

Automated:

- `zmedia_link`: matching against a fixture inventory: zero padding, empty
  name, `.heic` without a Digital Object, two Digital Objects expecting one
  file, `--since` with a deleted file; the same input twice gives
  byte-identical `link.jsonl`.
- arches-zmedia storage: `derivative_url` for thumbnail and iiif (percent
  encoding of `rel` with spaces and `~`), unknown kind and legacy name raise.
- arches-zmedia view: `thumbnail=true` → `THUMB_SIZE`; `size=500` → 500;
  `size=7` → Arches' default redirect; legacy file → Arches' behaviour;
  a forbidden file still `403`.
- archessql: SQL tests for the `files` upsert, a reload that keeps an
  unchanged file's row, a reload that drops a removed `file_id`, and a
  file-list value without `path` keeping its row.
- Fork (vitest): section empty, paged, sorted by identifier; tombstone
  fallback used only when the record's own image is empty.

Acceptance on GAP:

- `files` rows under `zmedia/digital_object/` equal the matched count;
  `unmatched.tsv` lists the rest, and every line has a reason.
- A second `zmedia_link` run without changes gives an empty delta.
- A trench report shows its images in identifier order, small size; a click
  opens the Digital Object.
- An artefact with no image of its own shows the first depicting image in
  its header.
- A Digital Object report shows its image.
