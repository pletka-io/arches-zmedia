"""Which zmedia derivative a /files/<id> request asks for (spec §4). Pure, so it is tested
without Arches; views.py is the glue."""


def choose_size(params, cfg):
    size = params.get("size")
    if size is not None:
        try:
            n = int(size)
        except ValueError:
            return None
        return n if n in cfg["SIZES"] else None
    if params.get("thumbnail", "false") != "false":
        return cfg["THUMB_SIZE"]
    return None


def redirect_target(name, storage, params, cfg):
    size = choose_size(params, cfg)
    if size is None or not hasattr(storage, "derivative_url"):
        return None
    try:
        return storage.derivative_url(name, "thumbnail", size)
    except ValueError:
        return None
