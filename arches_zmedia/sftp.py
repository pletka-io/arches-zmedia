"""SFTP to zmedia as media-<org>, with the instance's key and a pinned host key."""

from contextlib import contextmanager

import paramiko

# The pinned host key is ed25519 (archesctl key); offer nothing else, so
# paramiko never negotiates a host key type known_hosts lacks.
_NOT_ED25519 = [
    "rsa-sha2-512",
    "rsa-sha2-256",
    "ssh-rsa",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
]


# ponytail: one connection per storage call; pool when bulk uploads go through Arches
@contextmanager
def connect(cfg):
    client = paramiko.SSHClient()
    client.load_host_keys(cfg["KNOWN_HOSTS"])
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(
        cfg["SFTP_HOST"],
        port=cfg.get("SFTP_PORT", 2222),
        username=f"media-{cfg['ORG']}",
        key_filename=cfg["KEY_FILE"],
        allow_agent=False,
        look_for_keys=False,
        disabled_algorithms={"keys": _NOT_ED25519},
        timeout=30,
    )
    try:
        yield client.open_sftp()
    finally:
        client.close()


def ensure_dir(s, path):
    try:
        s.stat(path)
    except FileNotFoundError:
        s.mkdir(path)


def listdir(s, path):
    try:
        return set(s.listdir(path))
    except FileNotFoundError:
        return set()
