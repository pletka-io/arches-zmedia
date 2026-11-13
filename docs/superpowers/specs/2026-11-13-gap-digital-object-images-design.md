# GAP: Digital Object images, shown on the records they depict

Date: 2026-11-13
Status: draft, for review
Depends on: zmedia inventory API (kakugo spec
`2026-11-13-zmedia-inventory-design.md`): `GET /api/inventory/<org>/<spec>`.

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

1. Reads `/api/inventory/<org>/digital_object` from zmedia (`ZMEDIA["BASE_URL"]`,
   `ZMEDIA["ORG"]`, bearer token from `ZMEDIA_INVENTORY_TOKEN` in the
   instance env), zstd-encoded, streamed.
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
 "url": "https://media.delving.org/thumbnail/gap/digital_object/000001_DSC_0284.JPG/1000",
 "size": 5123456, "type": "image/jpeg",
 "status": "uploaded", "accepted": true}
```

The `file_id` is derived from the zmedia path, so a re-run produces the same
tiles and the delta is empty. The exact set of keys follows what Arches 8.1
writes for an uploaded file; the plan copies them from a tile the UI made.

With `--since`, only Digital Objects whose file changed or was deleted are
written; a deleted file's Digital Object gets an empty `image` tile.

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

## 4. Thumbnails at the right size

zmedia makes the thumbnails; Arches does not (`GENERATE_THUMBNAILS_ON_DEMAND`
stays off: turning it on would pull every original over SFTP to store a PNG
in the database). A zmedia thumbnail URL ends in its size,
`<BASE_URL>/thumbnail/<org>/<spec>/<rel>/<size>`, so a caller picks the size
by changing that suffix.

`zmedia_link` writes that URL (size 1000, the storage's `SIZE`) as the file
value's `url`, instead of `/files/<file_id>`. The gallery and the header
replace the trailing size: 300 in the grid, 1000 in the header. A file value
whose `url` has no numeric suffix (files uploaded through the UI keep
`/files/<id>`) is shown as is.

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
- A grid of thumbnails (the `url` with its size suffix set to 300, §4), each linking to its Digital
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
- archessql: SQL tests for the `files` upsert, a reload that keeps an
  unchanged file's row, a reload that drops a removed `file_id`, and a
  file-list value without `path` keeping its row.
- Fork (vitest): section empty, paged, sorted by identifier; size suffix
  swapped on a zmedia URL, `/files/<id>` left as is; tombstone
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
