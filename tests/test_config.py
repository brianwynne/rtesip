"""Tests for src.config.settings — load, save, merge, hardware info."""

import json
from pathlib import Path


def test_load_returns_defaults_when_no_file(tmp_data_dir):
    """load() with no config.json on disk returns the full DEFAULTS structure."""
    from src.config.settings import load, DEFAULTS

    cfg = load()
    assert set(cfg.keys()) == set(DEFAULTS.keys())
    assert cfg["sip"]["transport"] == "tls"
    assert cfg["audio"]["channels"] == 1
    assert cfg["base"]["product_name"] == "rtesip"


def test_save_and_load_round_trip(tmp_data_dir):
    """save() persists to disk and load() brings it back with the same values."""
    from src.config.settings import load, save

    cfg = load()
    cfg["sip"]["username"] = "alice"
    cfg["audio"]["bitrate"] = 128000
    save(cfg)

    reloaded = load()
    assert reloaded["sip"]["username"] == "alice"
    assert reloaded["audio"]["bitrate"] == 128000


def test_load_merges_defaults_for_missing_keys(tmp_data_dir):
    """If a saved config is missing keys added in a newer version, load() fills them from DEFAULTS."""
    from src.config.settings import load, save, DEFAULTS

    # Save a config with the sip section missing the 'codecs' key
    cfg = load()
    del cfg["sip"]["codecs"]
    save(cfg)

    reloaded = load()
    assert "codecs" in reloaded["sip"]
    assert reloaded["sip"]["codecs"] == DEFAULTS["sip"]["codecs"]


def test_update_section_merges(tmp_data_dir):
    """update_section() merges new keys into an existing section without clobbering others."""
    from src.config.settings import update_section, get_section

    update_section("sip", {"username": "bob", "registrar": "sip.example.com"})
    sip = get_section("sip")
    assert sip["username"] == "bob"
    assert sip["registrar"] == "sip.example.com"
    # Other keys untouched
    assert sip["transport"] == "tls"
    assert sip["reg_timeout"] == 600


def test_update_section_creates_new_section(tmp_data_dir):
    """update_section() creates a new section and returns it.

    Note: load() only merges DEFAULTS sections, so a custom section is
    persisted in the JSON file but not returned by get_section() after
    reload.  The return value of update_section() is authoritative.
    """
    from src.config.settings import update_section

    result = update_section("custom", {"foo": "bar"})
    assert result == {"foo": "bar"}

    # Verify it was written to disk
    import json
    from src.config.settings import _config_path
    raw = json.loads(_config_path().read_text())
    assert raw["custom"] == {"foo": "bar"}


def test_get_hardware_info_no_crash(tmp_data_dir):
    """get_hardware_info() returns a dict and doesn't crash even outside RPi."""
    from src.config.settings import get_hardware_info

    info = get_hardware_info()
    assert isinstance(info, dict)
    assert "serial" in info
    assert "model" in info
