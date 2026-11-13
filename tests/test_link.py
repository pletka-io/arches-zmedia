import json
import uuid

from arches_zmedia.link import Do, file_value, image_line, match, read_inventory

ROWS = [
    {"rel": "000001_DSC_0284.JPG", "hash": "h1", "size": 5, "mime": "image/jpeg", "width": 4, "height": 3, "last_changed": 1, "status": "ok", "deleted_at": None},
    {"rel": "000002_b.jpg", "hash": "h2", "size": 6, "mime": "image/jpeg", "width": 4, "height": 3, "last_changed": 1, "status": "ok", "deleted_at": None},
    {"rel": "000003_c.heic", "hash": "h3", "size": 7, "mime": "image/heic", "width": 4, "height": 3, "last_changed": 1, "status": "ok", "deleted_at": None},
    {"rel": "000004_gone.jpg", "hash": "h4", "size": 7, "mime": "image/jpeg", "width": 4, "height": 3, "last_changed": 1, "status": "deleted", "deleted_at": 9},
]
INV = read_inventory(json.dumps(r).encode() + b"\n" for r in ROWS)
P = "{identifier:06d}_{name}"


def ids(pairs):
    return sorted(d.resourceid for d, _ in pairs)


def test_match_zero_padding_and_leftovers():
    dos = [Do("r1", "1", "DSC_0284.JPG", False), Do("r2", "2", "b.jpg", False)]
    pairs, unmatched = match(dos, INV, P)
    assert ids(pairs) == ["r1", "r2"]
    assert ("file", "000003_c.heic", "no digital object") in unmatched


def test_match_reasons_for_digital_objects():
    dos = [
        Do("r3", "5", "", False),
        Do("r4", "x7", "a.jpg", False),
        Do("r5", "6", "sub/a.jpg", False),
        Do("r6", "7", "nope.jpg", False),
        Do("r7", "1", "DSC_0284.JPG", True),
    ]
    _, unmatched = match(dos, INV, P)
    reasons = {key: reason for kind, key, reason in unmatched if kind == "do"}
    assert reasons == {"r3": "empty name", "r4": "identifier not a number", "r5": "name with a slash", "r6": "file not found", "r7": "has an image already"}


def test_match_two_digital_objects_one_file():
    dos = [Do("r1", "1", "DSC_0284.JPG", False), Do("r8", "000001", "DSC_0284.JPG", False)]
    pairs, unmatched = match(dos, INV, P)
    assert pairs == []
    assert {("do", "r1", "duplicate: 000001_DSC_0284.JPG"), ("do", "r8", "duplicate: 000001_DSC_0284.JPG")} <= set(unmatched)


def test_deleted_file_matches_and_gives_an_empty_value():
    pairs, _ = match([Do("r9", "4", "gone.jpg", False)], INV, P)
    assert pairs[0][1]["status"] == "deleted"


def test_file_value_and_deterministic_ids():
    v = file_value("gap", "digital_object", INV["000001_DSC_0284.JPG"])
    fid = str(uuid.uuid5(uuid.NAMESPACE_URL, "zmedia:gap/digital_object/000001_DSC_0284.JPG"))
    assert v == {
        "file_id": fid, "name": "000001_DSC_0284.JPG", "path": "zmedia/digital_object/000001_DSC_0284.JPG",
        "url": f"/files/{fid}", "size": 5, "type": "image/jpeg", "status": "uploaded", "accepted": True,
        "renderer": "5e05aa2e-5db0-4922-8938-b4d2b7919733",
    }


def test_link_lines_are_deterministic():
    do = Do("11111111-1111-1111-1111-111111111111", "1", "DSC_0284.JPG", False)
    v = file_value("gap", "digital_object", INV["000001_DSC_0284.JPG"])
    a = image_line(do, "g", "ng", "n", v)
    assert a == image_line(do, "g", "ng", "n", v)
    line = json.loads(a)
    tile = line["tiles"][0]
    assert tile["tileid"] == str(uuid.uuid5(uuid.NAMESPACE_URL, f"zmedia-image:{do.resourceid}"))
    assert tile["nodegroup_id"] == "ng" and tile["data"] == {"n": [v]}
    assert image_line(do, "g", "ng", "n", None).count('"n": []') == 1  # deleted file: empty list


def test_image_tileid_is_the_one_image_line_uses():
    from arches_zmedia.link import image_tileid
    do = Do("11111111-1111-1111-1111-111111111111", "1", "a.jpg", False)
    assert json.loads(image_line(do, "g", "ng", "n", None))["tiles"][0]["tileid"] == image_tileid(do.resourceid)


def test_has_foreign_image():
    from arches_zmedia.link import has_foreign_image, image_tileid
    rid = "11111111-1111-1111-1111-111111111111"
    assert not has_foreign_image(rid, [])
    assert not has_foreign_image(rid, [image_tileid(rid)])
    assert has_foreign_image(rid, ["other"])
    assert has_foreign_image(rid, [image_tileid(rid), "other"])


def test_partial_skips_missing_files_silently():
    dos = [Do("r1", "1", "DSC_0284.JPG", False), Do("r6", "7", "nope.jpg", False), Do("r7", "8", "nope.jpg", True),
           Do("r3", "5", "", False)]
    pairs, unmatched = match(dos, INV, P, partial=True)
    assert ids(pairs) == ["r1"]
    assert [u for u in unmatched if u[0] == "do"] == [("do", "r3", "empty name")]
