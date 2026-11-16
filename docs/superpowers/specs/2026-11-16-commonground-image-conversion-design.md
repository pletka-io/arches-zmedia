# Common Ground: converting the `image` records to Digital Objects

Date: 2026-11-16
Status: mapping approved by Sjoerd (2026-11-16, question by question); for review as a whole
Addendum to: `2026-11-14-commonground-digital-objects-design.md` (decision 4,
§6 `--convert-image`).

## 1. Where this starts

The four models with images attached directly are done: artefact, finds
collection, archival object and textual work have 127,807 Digital Objects on
Common Ground, each depicting the record its file sits on, with gallery and
header image on the depicted records (`commonground-data`
`reports/images/digital-objects-runs.csv`).

Left are the 3,076 records of the `image` model
(`edef3275-b8f1-11ed-8e34-713b6788f6a4`). Decision 4 of the main spec: they
become Digital Objects keeping their own fields, and the `image` model is
retired. This addendum is the field mapping that decision asked to be shown
before anything is written, plus what the conversion needs around it.

Facts from `commonground-data` (pull of 2026-11-16):

- 3,076 records; 2,630 carry one file each, 446 carry none (the Asine
  excavation photographs of B07, loaded without their jpgs).
- On zmedia `commonground/image/`: 2,629 files (one of the 2,630 is missing).
- 16 of the model's ~110 nodes hold data; the rest are empty.
- No record of any other model links to an `image` record, so their ids can
  change and the model can be emptied without breaking a link.

## 2. Field mapping

Direct, no change needed (counts are records):

| `image` node | Records | → `digital_object` node |
|---|---|---|
| `image` (file-list) | 2,630 | `image`, as §6 of the main spec: `file_id` uuid5(namespace, "image", source file_id), `path: zmedia/digital_object/<name>` |
| `name_content`, `name_type` | 881 | `name_content`, `name_type` ("preferred name", in Labels) |
| `identifier_content`, `identifier_type` | 1,755 | `identifier_content`, `identifier_type` (same collection, ID Type) |
| `image__statement_content`, `image__statement_type` | 446 | `statement_content`, `statement_type` ("source folder", e.g. "Asine/Utgrävningsbilder") |
| `depicts_site` | 3,076 | `depicts_archaeological_site` |
| `depicts_place` | 435 | `depicts_place` |
| `depicts_feature` | 77 | `depicts_feature` |

Records without a name (2,195) get `name_content` = the file name, as the
generated Digital Objects do; one without a name and without a file gets no
name (its identifier shows in the descriptor).

Decided 2026-11-16 (Sjoerd):

| # | `image` node | Records | Decision |
|---|---|---|---|
| 1 | `image_type` = photograph (`55faa2fe…`) | 446 | → `type`. The node's collection, Digital Object Type (`36b2da4e…`), is empty: add photograph to it. |
| 2 | `identifier_type` = negative ID (`a10c5f16…`) | 874 | Keep. negative ID is in no collection today, on the `image` records too; add it to ID Type (`fa8db9d0…`), which both models use. |
| 3 | `depicts_type`: site 1,622, finds 337, grave 129, people 1 | 2,089 | → a statement: `statement_content` = the concept's label, `statement_type` = a new concept **depicts type** in Statement Type (`f7030023…`). |
| 4 | `associated_excavation` → archaeological excavation | 1,327 | → a new node **`depicts_archaeological_excavation`** on `digital_object` (§3). The creation-event link (the photo was made during the excavation) was considered and not chosen: no other model does it. |
| 5 | `associated_project` → archaeological project | 868 | → the existing `depicts_archaeological_project`. |
| 6 | `physical_carrier_type`: negative 839 (`6f4fa7e9…`), contact film 29 (`ae154f88…`) | 868 | → `creation_object_type_used` (the scan was made from a negative). Both concepts are in no collection today; add them to Physical Object Type (`13d354a4…`), which both nodes use. |
| 7 | `source_reference_statement_content` | 351 | All 351 read "Frödin and Persson 1938"; a textual work of exactly that name exists (`ea506dfe-ec93-45c5-9b70-02a514f333c2`). → `source_reference` linking to it; the text is not kept. |
| 8 | the 446 records without a file | 446 | Converted too: Digital Objects without an image. The file is attached when delivered (B07, B11). |
| 9 | ids | 3,076 | Digital Object id = uuid5(namespace, "image-record", old resourceinstanceid), so a rerun yields the same ids. The `image` records are deleted in the same push; the model is retired afterwards. Their old report URLs stop working. |

Relations are written as the target node's own: `ontologyProperty`
`P129_is_about` (every `depicts_*` node on `digital_object` uses it, and so
does the new one), never the `P138i` the `image` links carry.

Nodes without a counterpart are listed in the generator's report with their
counts, never dropped silently. After this mapping that list is empty for the
16 nodes in use.

## 3. Model change: `depicts_archaeological_excavation`

Through Pletka, like the 11 `depicts_*` nodes before it (main spec §3): edit
the `digital_object` tree in weave-si, generate the pack, graph-push it into
Common Ground (preview, sync). Shape copied from `depicts_archaeological_project`:
resource-instance-list, `P129_is_about`, target graph archaeological
excavation (`50871e6f-55cf-11ed-a689-1ff50755770b`), its own card in the
depicts group. No tile data touched.

## 4. Thesaurus additions

One RDM change in `commonground-data` `config/rdm/rdm.jsonl`, pushed with
`worktree rdm-push` (preview, sync):

- Digital Object Type ← member photograph (`55faa2fe…`).
- ID Type ← member negative ID (`a10c5f16…`).
- Physical Object Type ← members negative (`6f4fa7e9…`) and contact film (`ae154f88…`).
- Statement Type ← new concept **depicts type** (prefLabel en).

Items 2 and 6 also fix the existing `image` records, whose values are outside
their collections today.

## 5. Generator: `--convert-image` (arches-fleet kit)

```
archessql worktree generate digital-objects --convert-image [--limit N] [--dry-run]
```

Reads `resources/image_<graphid>/*.json`, the pulled `digital_object`
inventory and the thesaurus; per `image` record:

1. writes one Digital Object per §2 into `resources/digital_object_<graphid>/`;
2. deletes the `image` record's file from the worktree;
3. writes `reports/generate-digital-objects-image-<run>.json` with
   `resources_changed_ids` (the new Digital Objects) and
   **`resources_deleted_ids`** (the `image` records), and per-node counts,
   unmapped nodes, files not in the inventory.

Pack today makes tombstones only for a whole-tree pack (`--all`); a
`--from-report` pack fails on an id without a file. Change: `pack
--from-report` also reads `resources_deleted_ids` and writes a tombstone for
each id that is in the manifest and has no file. A whole-tree push is not an
option on Common Ground: 310,653 resources, over `max_stage_resources`
(100,000).

The concept ids for decisions 1, 2, 3 and 6 are looked up by label in the
pulled thesaurus, so the generator refuses to run before §4 is synced (a
missing concept or collection member is an error, not a skip). Likewise it
refuses while `digital_object` lacks `depicts_archaeological_excavation`
(§3).

A rerun on an unchanged worktree writes nothing. A Digital Object changed by
hand after the conversion is reported, not overwritten (as for `--model`).

Tests, test-first, in `digital_objects_test.go`: each row of §2 on a fixture
record; the record without a file; the depicts-type statement; the source
reference link; ids stable across runs; refusals for a missing concept and a
missing node; the report's `resources_deleted_ids`; pack tombstones from a
report.

## 6. Order

1. §4 thesaurus additions: edit, `rdm-push` preview, sync, pull.
2. §3 node through Pletka: weave-si, pack, graph-push preview, sync, pull.
3. §5 kit: PR (generator and pack), merge, nixops pin and fleet-1 deploy
   only if the loader changes (it should not), kit release, data-repo pins.
4. On shoku: `cg-link-digital-object.sh image` (2,629 files into
   `digital_object/`), wait for zmedia's index to list them.
5. `worktree pull`, `generate digital-objects --convert-image --dry-run`,
   read the report, the real run, commit.
6. `worktree push --from-report <report> --allow-deletes` (3,076 deletes,
   above the delete cap of 1,000): preview must show 3,076 resource inserts,
   3,076 resource deletes, nothing else on other graphs; then `--sync`.
7. Galleries: `report-images --model <slug>` for archaeological_excavation,
   archaeological_project, archaeological_site, place and feature (idempotent:
   a layout that has its gallery is unchanged), `report-push`, browser check.
8. Pull baseline, `digital-objects-runs.csv` row, push.
9. Retire the `image` model: once it has no records, remove it from weave-si
   and Common Ground (separate step, its own preview).

## 7. Not in scope

- The 1 `image` file missing on zmedia and the 446 undelivered Asine files:
  BACKLOG B07/B11, Denitsa.
- Removing the direct file entries from the other models (main spec decision 3).
- The `unlinked` files (18,617 where ~8,760 were expected): investigated
  separately before any generation.
