from types import SimpleNamespace

from django.core.exceptions import ObjectDoesNotExist

from arches_zmedia import naming


def file_on(slug):
    return SimpleNamespace(tile=SimpleNamespace(resourceinstance=SimpleNamespace(graph=SimpleNamespace(slug=slug))))


class NoTile:
    @property
    def tile(self):
        raise ObjectDoesNotExist


def test_file_on_tile_goes_to_its_spec():
    assert naming.generate_filename(file_on("image"), "a b.jpg") == "zmedia/image/a b.jpg"


def test_file_without_tile_stays_local():
    assert naming.generate_filename(SimpleNamespace(tile=None), "x.jpg") == "uploadedfiles/x.jpg"
    assert naming.generate_filename(NoTile(), "x.jpg") == "uploadedfiles/x.jpg"


def test_generator_keeps_only_the_basename():
    assert naming.generate_filename(file_on("image"), "../../etc/x.jpg") == "zmedia/image/x.jpg"


def test_zmedia_key():
    assert naming.zmedia_key("zmedia/image/x.jpg") == ("image", "x.jpg")
    assert naming.zmedia_key("uploadedfiles/x.jpg") is None
    assert naming.zmedia_key("zmedia/image") is None
