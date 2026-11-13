from arches_zmedia.push import plan_push


def test_plan_push(tmp_path):
    for n in ("a.jpg", "b.jpg", "o.jpg"):
        (tmp_path / n).write_bytes(b"x")
    rows = [
        ("uploadedfiles/a.jpg", "image"),  # zmedia has it
        ("uploadedfiles/b.jpg", "image"),  # to upload
        ("uploadedfiles/b.jpg", "image"),  # same row twice: once
        ("uploadedfiles/o.jpg", None),  # no tile: unlinked
        ("uploadedfiles/gone.jpg", "image"),  # not on disk
        ("zmedia/image/z.jpg", "image"),  # already a zmedia name
    ]
    remote = {"image": {"a.jpg"}}
    local = lambda name: str(tmp_path / name.split("/", 1)[1])
    todo, missing = plan_push(rows, remote, local)
    assert todo == [(str(tmp_path / "b.jpg"), "image", "b.jpg"), (str(tmp_path / "o.jpg"), "unlinked", "o.jpg")]
    assert missing == ["uploadedfiles/gone.jpg"]
