from contextlib import contextmanager

import pytest
from django.core.files.base import ContentFile

from arches_zmedia.storage import ZmediaStorage
from fakes import FakeSFTP, connect_to

THUMB = "https://media.example/thumbnail/cg"


def make(tmp_path, specs=None, fake=None):
    specs = specs or {}
    fake = fake or FakeSFTP()
    st = ZmediaStorage(resolve=specs.get, connect=connect_to(fake), location=str(tmp_path))
    return st, fake


def test_url_zmedia_name(tmp_path):
    st, _ = make(tmp_path)
    assert st.url("zmedia/image/x.jpg") == f"{THUMB}/image/x.jpg/1000"


def test_url_quotes_name(tmp_path):
    st, _ = make(tmp_path)
    assert st.url("zmedia/image/a b#1?é.jpg") == f"{THUMB}/image/a%20b%231%3F%C3%A9.jpg/1000"


def test_url_legacy_resolved(tmp_path):
    st, _ = make(tmp_path, {"uploadedfiles/x.jpg": "finds_collection"})
    assert st.url("uploadedfiles/x.jpg") == f"{THUMB}/finds_collection/x.jpg/1000"


def test_url_legacy_unlinked(tmp_path):
    st, _ = make(tmp_path, {"uploadedfiles/o.jpg": "unlinked"})
    assert st.url("uploadedfiles/o.jpg") == f"{THUMB}/unlinked/o.jpg/1000"


def test_url_local_name(tmp_path):
    st, _ = make(tmp_path)
    assert st.url("uploadedfiles/tmp/load1/a.csv") == "/files/uploadedfiles/tmp/load1/a.csv"


def test_save_zmedia_name_uploads_into_spec_dir(tmp_path):
    st, fake = make(tmp_path)
    name = st.save("zmedia/image/x.jpg", ContentFile(b"jpeg"))
    assert name == "zmedia/image/x.jpg"
    assert fake.files["/cg/image/x.jpg"] == b"jpeg"
    assert not (tmp_path / "zmedia").exists()
    assert st.exists(name) and st.size(name) == 4


def test_save_does_not_overwrite(tmp_path):
    st, fake = make(tmp_path)
    st.save("zmedia/image/x.jpg", ContentFile(b"one"))
    second = st.save("zmedia/image/x.jpg", ContentFile(b"two"))
    assert second != "zmedia/image/x.jpg" and second.startswith("zmedia/image/x_")
    assert fake.files["/cg/image/x.jpg"] == b"one"


def test_save_local_name(tmp_path):
    st, fake = make(tmp_path)
    st.save("uploadedfiles/tmp/l1/a.csv", ContentFile(b"a,b"))
    assert (tmp_path / "uploadedfiles/tmp/l1/a.csv").read_bytes() == b"a,b"
    assert fake.files == {}


def test_save_failure_raises(tmp_path):
    @contextmanager
    def down(cfg):
        raise OSError("connection refused")
        yield

    st = ZmediaStorage(resolve={}.get, connect=down, location=str(tmp_path))
    with pytest.raises(OSError):
        st.save("zmedia/image/x.jpg", ContentFile(b"jpeg"))


def test_delete_keeps_the_original(tmp_path):
    st, fake = make(tmp_path)
    st.save("zmedia/image/x.jpg", ContentFile(b"jpeg"))
    st.delete("zmedia/image/x.jpg")
    assert "/cg/image/x.jpg" in fake.files


def test_derivative_url_thumbnail_any_size(tmp_path):
    st, _ = make(tmp_path)
    assert st.derivative_url("zmedia/digital_object/000001_DSC 0284.JPG", "thumbnail", 300) == (
        "https://media.example/thumbnail/cg/digital_object/000001_DSC%200284.JPG/300"
    )


def test_derivative_url_iiif_encodes_tilde_and_slash(tmp_path):
    st, _ = make(tmp_path)
    assert st.derivative_url("zmedia/do/a~b c.jpg", "iiif") == "https://media.example/iiif/3/cg~do~a%7Eb%20c.jpg"
    assert st.derivative_url("zmedia/do/sub/x.jpg", "iiif") == "https://media.example/iiif/3/cg~do~sub%2Fx.jpg"


def test_derivative_url_refuses_unknown_kind_and_legacy_names(tmp_path):
    st, _ = make(tmp_path)
    with pytest.raises(ValueError):
        st.derivative_url("zmedia/do/a.jpg", "deepzoom")
    with pytest.raises(ValueError):
        st.derivative_url("uploadedfiles/a.jpg", "thumbnail", 300)
    with pytest.raises(ValueError):
        st.derivative_url("zmedia/do/a.jpg", "thumbnail")  # thumbnail needs a size
