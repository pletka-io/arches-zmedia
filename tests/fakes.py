import os
from contextlib import contextmanager
from types import SimpleNamespace


class FakeSFTP:
    """The slice of paramiko's SFTPClient the package uses, in memory."""

    def __init__(self, org="cg"):
        self.files = {}
        self.dirs = {f"/{org}"}

    def stat(self, p):
        if p in self.files:
            return SimpleNamespace(st_size=len(self.files[p]))
        if p in self.dirs:
            return SimpleNamespace(st_size=0)
        raise FileNotFoundError(p)

    def mkdir(self, p):
        assert os.path.dirname(p) in self.dirs, f"parent of {p} missing"
        self.dirs.add(p)

    def putfo(self, fl, p):
        assert os.path.dirname(p) in self.dirs, f"no dir for {p}"
        self.files[p] = fl.read()

    def put(self, local, p):
        with open(local, "rb") as fh:
            self.putfo(fh, p)

    def listdir(self, p):
        if p not in self.dirs:
            raise FileNotFoundError(p)
        return [k.rsplit("/", 1)[1] for k in self.files if k.rsplit("/", 1)[0] == p]


def connect_to(fake):
    @contextmanager
    def connect(cfg):
        yield fake

    return connect
