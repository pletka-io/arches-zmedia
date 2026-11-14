# Common Ground: a Digital Object per image, shown on the records it depicts

Date: 2026-11-14
Status: draft, for review (revision 3: generator and GAP linker in the
workbench, files under `digital_object/` on zmedia)
Builds on: `2026-11-13-gap-digital-object-images-design.md` (GAP, live 2026-11-14:
17,855 Digital Objects linked, gallery + header on the depicted records).

## 1. Goal

Common Ground keeps ~140,000 images as files attached directly to records
(archival objects 77,817, finds collections 30,354, textual works 25,543,
artefacts 1,019, a few hundred on other models), 9,067 files on no record, and
3,076 records of an `image` model (2,630 with a file). All files are on zmedia
under `commonground/<model>/` and served through the arches-zmedia storage
backend. The `digital_object` model exists with 0 records.

After this work every image is a Digital Object: its `image` node holds the
file, now under `commonground/digital_object/` on zmedia, a `depicts_<model>`
node points at the record it shows, and that record's report shows the image
in its gallery and header exactly as GAP does. Nothing is asked of the data
editor; she can enrich the generated records later, in the same workbench.

## 2. Decisions (Sjoerd, 2026-11-14)

1. The image carrier is `digital_object`: same model, report config and file
   layout as GAP.
2. Digital Objects are generated from the existing file entries, one per file.
3. The original file entries stay on the records; removing them is a later,
   separate step per model once the gallery shows the same images.
4. The 3,076 `image` records are converted to Digital Objects keeping their own
   fields; the `image` model is retired afterwards. Field mapping is shown to
   Sjoerd before anything is written.
5. Order: artefact first (end-to-end check), then the `image` conversion, then
   finds_collection, textual_work, archival_object, and files on no record last.
6. The link is GAP's shape: `depicts_<model>` nodes on the Digital Object.
7. The model change runs through Pletka: edit the weave-si tree, generate the
   pack, push it into Common Ground (section 3). First full-chain run.
8. Generation is an `archessql` workbench command, not a manage.py command: it
   writes resource JSON into the data repo, so the result is linted, diffed
   and reviewed in git and pushed with the normal `worktree push` loop.
9. Files live under `commonground/digital_object/` on zmedia, like GAP's, so
   the layout matches how new uploads will work (upload into the Digital
   Object spec). They get there as hard links; each model's old folder is
   pruned when its old file entries are removed (decision 3).
10. The workbench knows which files exist on zmedia from the inventory, pulled
    through the loader (`worktree pull`); nobody outside fleet-1 needs a dash
    token.
11. GAP's linker (`zmedia_link`) becomes a kit command too (§6.1): one way of
    working, in the workbench, for every instance.

## 3. Model change through Pletka

### 3.0 Gate: does the pack match live by id? (read-only)

Graph push matches graphs and nodes by id. weave-si was converted from Common
Ground's live graphs and its sidecar keeps the live graph id
(`generators/arches/digital_object/graph.yaml`); whether the generated pack
also carries the live node ids is not established.

Test: generate the pack from weave-si main unchanged, put its graph files in a
throwaway commonground-data worktree's `config/graphs/` and run
`worktree graph-push --graph digital_object` (preview only, never `--sync`).

- `unchanged` (0 ops): ids match, continue with 3.1.
- remove/add of every node: the generator mints its own node ids. Then the
  first job is the id mapping of the graph-push design §11 (alias match →
  live node id in the sidecar), its own PR in pletka-platform, and this gate
  runs again.
- Fallback if that mapping is not wanted now: add the fields in the Arches
  designer on Common Ground (Draft a Model Update → Publish Draft), pull into
  commonground-data, and convert the result back into weave-si. Tested route
  (graph push criterion 2, 2026-11-05), but Pletka is then not the source.

### 3.1 Edit

In weave-si (PR): on SIM.8 (Digital Object) add one placement per depicted
model, `depicts_<slug>` for archival_object, finds_collection, textual_work,
artefact, feature, archaeological_site, place, trench, person,
archaeological_survey, archaeological_project, each a resource-instance-list
whose target is that model, CRM path as GAP's (`P62_depicts`; GAP's
`depicts_*` nodes are the reference for ontology property, card and widget).
Aliases in `generators/arches/digital_object/aliases.yaml`. `make
tree-validate` green apart from the known 363 live-modelling findings.

### 3.2 Push

Pack from the merged tree; graph files into commonground-data `config/graphs/`
(only `digital_object` changes); `worktree graph-push --graph digital_object`:

- preview must show only `add_node` / `add_card` ops for the eleven fields and
  0 destructive;
- `--sync` (data token suffices: additive), publish (`graph publish --update`,
  `has_unpublished_changes` set), reindex skipped (no resources yet);
- the pull afterwards shows the same eleven fields in `config/graphs/`, the
  compare against the pack (`worktree graph-compare --pack`) shows no
  difference for `digital_object`;
- rollback by `push_id` stays available until the first data load.

Drafts: the push refuses while a draft is open and publishes directly; an
Arches draft route is not part of this work.

## 4. The zmedia inventory in the workbench (arches-fleet)

New loader route `GET /v1/data/zmedia/inventory/<spec>[?since=]`: the loader
calls dash's `/api/inventory/<org>/<spec>` with the instance's app token
(`/etc/arches/<slug>/zmedia-inventory.token`, already there) and streams the
NDJSON through. Data-token scope; a 503 from dash (array not mounted) passes
through as 503, never as an empty list.

`worktree pull` fetches the inventory of every spec the generator needs into
`.archessql/zmedia/<spec>.ndjson` (git-ignored, refreshed on every pull, like
`.archessql/ontologies/`). Commands read it offline. Rows with
`rel_invalid: true` are reported, never matched.

## 5. Files into `digital_object/` on zmedia (shoku)

One script on shoku, per model in the order of §2.5:
`ln <array>/commonground/<model>/<file> <array>/commonground/digital_object/<file>`
for every file of that model. Names are unique across all folders: 140,495
distinct names in 149,261 files, and the 8,766 names found in two folders
(8,747 textual_work + unlinked, the rest small pairs) have identical content
(sha256, 2026-11-14), so one flat folder holds them all; an existing link with
the same content is skipped, a different one stops the script.

zmedia ingest picks the new paths up as new originals in spec `digital_object`
and builds their derivatives (thumbnails) once. The old paths stay valid: the
records' old entries still resolve to `<model>/` through arches-zmedia's
legacy lookup. Pruning a model's old folder is part of removing its old file
entries (out of scope here).

## 6. Generating the Digital Objects (arches-fleet kit)

```
archessql worktree generate digital-objects --model artefact [--limit N]
archessql worktree generate digital-objects --unlinked
archessql worktree generate digital-objects --convert-image
```

Reads the worktree (`resources/<model>_<graphid>/*.json`, the file-list values
with `file_id` and `name`) and the pulled inventory of `digital_object`; writes
one resource per file into `resources/digital_object_<graphid>/` and a report
`reports/generate-digital-objects-<model>-<run>.json` with
`resources_changed_ids`, as every workbench fix does:

| Node | Value |
|---|---|
| resourceinstanceid | uuid5(fixed namespace, source file_id): a rerun yields the same ids |
| `name_content` | the file name |
| `image` | one file-list entry: `file_id` uuid5(namespace, "image", source file_id), `name`, `path: zmedia/digital_object/<name>`, type and renderer from the source entry |
| `depicts_<model>` | the record the source entry sits on (absent for `--unlinked`) |

The `path` key makes `delta_sync` write the `files` row (arches-fleet #71); the
storage backend serves `zmedia/digital_object/<name>` as it does GAP's.

Files not in the `digital_object` inventory (the 3,164 of commonground-data
B31, or a model not yet linked in §5) are skipped and listed in the report
with their reason. A rerun on an unchanged worktree changes nothing (no git
diff). `--convert-image` maps each `image` record field by field (name,
statements, identifiers, creation; links into `image` such as
`digital_carrier` become `depicts_*`); its mapping table is reviewed before
the first write, and fields without a counterpart are listed, not dropped.

Lint: the coverage/lint run validates the generated resources against the
graph like any delivery (cardinality, references, concepts).

### 6.1 Linking existing Digital Objects (GAP's case), also a kit command

`zmedia_link` (arches-zmedia, manage.py, used for GAP on 2026-11-14) moves into
the kit beside the generator, on the same pulled inventory:

```
archessql worktree link digital-objects --pattern "{identifier:06d}_{name}" \
    --identifier-node identifier_content --name-node name_content --image-node image
```

Same matching rules as `zmedia_link` (every name value tried, names with a
slash refused, unmatched files and objects reported), but it writes the
`image` values into the worktree's Digital Object resources and a report,
instead of a JSONL file in the pod; loading is `worktree push --from-report`.
Acceptance: run on gap-data, the result equals what GAP holds now (17,855
linked, the 302 of B32 unmatched), so the pushed preview is empty. Then
`zmedia_link` is removed from arches-zmedia (a major-version note in its
changelog), which keeps only the storage backend and the report config.

## 7. Load and display, per step

1. §5 links for the model; zmedia ingest done (inventory count = files).
2. `worktree pull` (inventory refreshed), `worktree generate digital-objects`.
3. Lint; review the report and the git diff; commit.
4. `worktree push --from-report <report>`: stage, preview (`tile` mode:
   inserts only), read the counts back, `--sync`. Never `resource` mode.
5. Index the new Digital Objects (loader reindex of touched resources).
6. `customize_modular_report_config --force --slug <model>`: gallery and
   header, as on GAP.

Before the first step: reinstall the SQL pack on Common Ground's database
(`archessql install --profile all`) so `delta_sync` writes `files` rows, and a
kit release carrying §4 and §6 (tag, nixops pin, fleet-1 deploy, data repo
pins).

## 8. Acceptance

Per step:

- Digital Objects generated = files of the model − skipped; a second generate
  leaves the worktree unchanged.
- After sync: `files` rows under `zmedia/digital_object/` = new `image` tiles;
  the next pull equals the committed worktree.
- `/files/<id>?thumbnail=true` → 302 to zmedia `digital_object/…/300`, plain
  → `/1000`.
- Gallery API on one record of the model returns its Digital Objects; one
  record per model checked in the browser.
- The records' original file entries are untouched (count before = after) and
  still display (they resolve to the old folder).

For the model change: preview additive only, pull equals pack, rollback id
recorded. For the inventory route: 200 with the same lines dash gives, 503
passed through.

## 9. Not in scope

IIIF manifests per record; the data editor enriching generated Digital
Objects; removing the records' original file entries and pruning the old
zmedia folders; retiring the `image` model (after its conversion is checked);
an Arches draft route for graph push; GAP-style names (`<identifier>_<name>`)
for new uploads.

Uploads need no change: arches-zmedia files an upload under the slug of the
model it is made on, so an image uploaded on a Digital Object's `image` node
already lands in `commonground/digital_object/` (as on GAP). Only uploads on
a record's own file-list node (archival object etc.) go to that model's
folder; those nodes go when the old entries are removed.

## 10. Open

- Gate 3.0 outcome decides whether the id mapping work comes first.
- `depicts_*` for models not in the list (sample, group, layer) if files turn
  up there.
