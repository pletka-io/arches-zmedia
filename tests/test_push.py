import sys
import types

from arches_zmedia import naming, sftp
from arches_zmedia.push import plan_push
from fakes import FakeSFTP


def test_plan_push(tmp_path):
    for n in ("a.jpg", "b.jpg", "o.jpg"):
        (tmp_path / n).write_bytes(b"x")
    (tmp_path / "c.jpg").write_bytes(b"other")
    rows = [
        ("uploadedfiles/a.jpg", "image"),  # zmedia has it, same size
        ("uploadedfiles/b.jpg", "image"),  # to upload
        ("uploadedfiles/b.jpg", "image"),  # same row twice: once
        ("uploadedfiles/o.jpg", None),  # no tile: unlinked
        ("uploadedfiles/gone.jpg", "image"),  # not on disk
        ("uploadedfiles/c.jpg", "image"),  # zmedia has another file by that name
        ("zmedia/image/z.jpg", "image"),  # already a zmedia name
    ]
    remote = {"image": {"a.jpg": 1, "c.jpg": 1}}
    local = lambda name: str(tmp_path / name.split("/", 1)[1])
    todo, missing, conflicts = plan_push(rows, remote, local)
    assert todo == [(str(tmp_path / "b.jpg"), "image", "b.jpg"), (str(tmp_path / "o.jpg"), "unlinked", "o.jpg")]
    assert missing == ["uploadedfiles/gone.jpg"]
    assert conflicts == ["uploadedfiles/c.jpg"]


def test_upload_lands_whole_or_not_at_all(tmp_path):
    f = tmp_path / "x.jpg"
    f.write_bytes(b"jpeg")
    fake = FakeSFTP()
    fake.dirs.add("/cg/image")
    sftp.upload(fake, str(f), "/cg/image/x.jpg")
    assert fake.files == {"/cg/image/x.jpg": b"jpeg"}
    assert sftp.listdir(fake, "/cg/image") == {"x.jpg": 4}


def test_legacy_spec_does_not_cache_misses(monkeypatch):
    answers = {"uploadedfiles/x.jpg": []}

    class Q:
        def __init__(self, path):
            self.path = path

        def values_list(self, *a, **k):
            return answers[self.path]

    File = types.SimpleNamespace(objects=types.SimpleNamespace(filter=lambda path: Q(path)))
    mod = types.ModuleType("arches.app.models.models")
    mod.File = File
    for m in ("arches", "arches.app", "arches.app.models"):
        monkeypatch.setitem(sys.modules, m, types.ModuleType(m))
    monkeypatch.setitem(sys.modules, "arches.app.models.models", mod)
    naming._found.clear()
    assert naming.legacy_spec("uploadedfiles/x.jpg") is None  # no row yet
    answers["uploadedfiles/x.jpg"] = [None]
    assert naming.legacy_spec("uploadedfiles/x.jpg") == naming.UNLINKED  # row, no tile yet
    answers["uploadedfiles/x.jpg"] = ["image"]
    assert naming.legacy_spec("uploadedfiles/x.jpg") == "image"  # tile set: seen at once
