# Common Ground: a Digital Object per image, shown on the records it depicts

Date: 2026-11-14
Status: draft, for review
Builds on: `2026-11-13-gap-digital-object-images-design.md` (GAP, live 2026-11-14:
17,855 Digital Objects linked, gallery + header on the depicted records).

## 1. Goal

Common Ground keeps ~140,000 images as files attached directly to records
(archival objects 77,817, finds collections 30,354, textual works 25,543,
artefacts 1,019, a few hundred on other models), 9,067 files on no record, and
3,076 records of an `image` model (2,630 with a file). All files are on zmedia
under `commonground/<spec>/` and served through the arches-zmedia storage
backend. The `digital_object` model exists with 0 records.

After this work every image is a Digital Object: its `image` node holds the
file, a `depicts_<model>` node points at the record it shows, and that record's
report shows the image in its gallery and header exactly as GAP does. Nothing
is asked of the data editor; she can enrich the generated records later.

## 2. Decisions (Sjoerd, 2026-11-14)

1. The image carrier is `digital_object`, same model, linker and report config
   as GAP.
2. Digital Objects are generated from the existing `files` rows, not from a
   delivery: one per file.
3. The original file entries stay on the records; removing them is a later,
   separate step per model once the gallery shows the same images.
4. The 3,076 `image` records are converted to Digital Objects keeping their own
   fields; the `image` model is retired afterwards. Field mapping is shown to
   Sjoerd before anything is written.
5. Order: artefact first (end-to-end check), then the `image` conversion, then
   finds_collection, textual_work, archival_object, and files on no record last.
6. The link is GAP's shape: `depicts_<model>` nodes on the Digital Object.
7. The model change runs through Pletka: edit the weave-si tree, generate the
   pack, push it into Common Ground (section 3). This is the first full-chain
   run: model change in Pletka, push, data load, diff, insert, reindex.

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

## 4. Generating the Digital Objects

New management command in arches-zmedia, beside `zmedia_link`:

```
python manage.py zmedia_generate --model artefact --out DIR [--limit N]
python manage.py zmedia_generate --unlinked --out DIR
```

Per `files` row in scope (row on a tile of a `--model` record, or on no tile
for `--unlinked`), one Digital Object resource in the loader's JSONL shape:

| Node | Value |
|---|---|
| resourceinstanceid | uuid5(fixed namespace, source fileid): a rerun yields the same ids |
| `name_content` | file name (basename of the zmedia name) |
| `image` | a new File row pointing at the same zmedia name, `zmedia/<spec>/<file>`, spec from the inventory (the file's directory on zmedia, not the record's model) |
| `depicts_<model>` | the record the source row's tile belongs to (absent for `--unlinked`) |

Source rows whose file is not on zmedia (the 3,164 of commonground-data B31)
are skipped and listed in `DIR/unmatched.tsv` with the reason; the zmedia
inventory API (`/api/inventory/commonground/<spec>`) is the existence check,
as in `zmedia_link`. Output: `link.jsonl`, `unmatched.tsv`, counts. Byte-
identical on a rerun. Never writes to the database.

## 5. Converting the `image` records

Separate mode `zmedia_generate --convert-image`: each `image` record becomes a
Digital Object with a new resourceinstanceid (uuid5 of the image record id,
so the image record and its Digital Object coexist until retirement), its
name, statements, identifiers and creation mapped field by field, and what the
image depicted (`digital_carrier` and the other links into `image`) carried
over to `depicts_*`. The field-by-field table is a deliverable for review
before the first write; fields with no Digital Object counterpart are listed,
not dropped silently.

## 6. Load and display, per step

Same procedure as GAP, per model in the order of §2.5:

1. `zmedia_generate` → review `unmatched.tsv` and counts.
2. `archessql resource import-jsonl` → `show_delta_preview('tile')`: inserts
   only, count = Digital Objects × tiles per object.
3. `delta_sync('tile')`; never `resource` mode.
4. Index the new Digital Objects (`es index_resources_by_type` for
   digital_object, or the loader's reindex of touched resources).
5. `customize_modular_report_config --force --slug <model>`: gallery and
   header, as on GAP.

Before the first step: reinstall the SQL pack on Common Ground's database
(`archessql install --profile all`) so `delta_sync` writes `files` rows
(arches-fleet #71).

## 7. Acceptance

Per step:

- Digital Objects created = files in scope − unmatched; a second generate is
  byte-identical.
- `files` rows under the step's names = new `image` tiles.
- `/files/<id>?thumbnail=true` → 302 to zmedia `/300`, plain → `/1000`.
- Gallery API on one record of the model returns its Digital Objects; one
  record per model checked in the browser.
- The original file entries on the records are untouched (count before =
  after).

For the model change: preview additive only, pull equals pack, rollback id
recorded.

## 8. Not in scope

IIIF manifests per record; the data editor enriching generated Digital
Objects; removing the records' original file entries; retiring the `image`
model (after §5 is checked); an Arches draft route for graph push; the 9,067
files on no record beyond generating their Digital Objects.

## 9. Open

- Gate 3.0 outcome decides whether the id mapping work comes first.
- `depicts_*` for models not in the list (sample, group, layer) if files turn
  up there.
- The 8,760 files under `commonground/unlinked/` on zmedia that are not in the
  copy from fleet-1 (checksum comparison 2026-11-14): where they came from,
  before `--unlinked` runs.
