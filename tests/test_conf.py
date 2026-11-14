from arches_zmedia.conf import settings


def test_without_key_only_zmedia(tmp_path):
    s = settings("gap", etc=str(tmp_path))
    assert set(s) == {"ZMEDIA"}
    assert s["ZMEDIA"]["ORG"] == "gap"
    assert s["ZMEDIA"]["KEY_FILE"] == f"{tmp_path}/gap/zmedia_ed25519"
    assert s["ZMEDIA"]["KNOWN_HOSTS"] == f"{tmp_path}/gap/zmedia_known_hosts"


def test_with_key_switches_storage(tmp_path):
    (tmp_path / "gap").mkdir()
    (tmp_path / "gap" / "zmedia_ed25519").write_text("k")
    s = settings("gap", etc=str(tmp_path))
    assert s["FILENAME_GENERATOR"] == "arches_zmedia.naming.generate_filename"
    assert s["STORAGES"]["default"]["BACKEND"] == "arches_zmedia.storage.ZmediaStorage"
    assert "staticfiles" in s["STORAGES"]


def test_settings_defaults_for_derivatives_and_inventory(tmp_path):
    z = settings("gap", etc=str(tmp_path))["ZMEDIA"]
    assert z["THUMB_SIZE"] == 300
    assert z["SIZES"] == [100, 300, 500, 1000]
    assert z["INVENTORY_TOKEN_FILE"] == f"{tmp_path}/gap/zmedia-inventory.token"
    assert "INVENTORY_URL" not in z
