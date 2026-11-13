from arches_zmedia.derivatives import choose_size, redirect_target

CFG = {"THUMB_SIZE": 300, "SIZES": [100, 300, 500, 1000]}


class Store:
    def derivative_url(self, name, kind, size=None):
        if not name.startswith("zmedia/"):
            raise ValueError(name)
        return f"D:{name}:{kind}:{size}"


def test_choose_size():
    assert choose_size({"thumbnail": "true"}, CFG) == 300
    assert choose_size({"size": "500"}, CFG) == 500
    assert choose_size({"size": "7"}, CFG) is None
    assert choose_size({"size": "abc"}, CFG) is None
    assert choose_size({"thumbnail": "false"}, CFG) is None
    assert choose_size({}, CFG) is None
    assert choose_size({"thumbnail": "true", "size": "1000"}, CFG) == 1000  # an explicit size wins


def test_redirect_target():
    assert redirect_target("zmedia/do/a.jpg", Store(), {"thumbnail": "true"}, CFG) == "D:zmedia/do/a.jpg:thumbnail:300"
    assert redirect_target("zmedia/do/a.jpg", Store(), {}, CFG) is None
    assert redirect_target("uploadedfiles/a.jpg", Store(), {"thumbnail": "true"}, CFG) is None
    assert redirect_target("zmedia/do/a.jpg", object(), {"thumbnail": "true"}, CFG) is None  # not our storage
