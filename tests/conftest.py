"""Shared pytest fixtures for rtesip tests."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path, monkeypatch):
    """Redirect DATA_DIR and CONFIG_DIR to a temp directory for every test."""
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    data_dir.mkdir()
    config_dir.mkdir()

    import src.config.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings_mod, "CONFIG_DIR", config_dir)

    # Also patch the contacts module's reference to DATA_DIR
    import src.api.routes.contacts as contacts_mod
    monkeypatch.setattr(contacts_mod, "CONTACTS_FILE", data_dir / "contacts.json")

    # Patch the updater's version file so GET /api/update/version works
    import src.update.updater as updater_mod
    monkeypatch.setattr(updater_mod, "CURRENT_VERSION_FILE", data_dir / "version.json")

    # Patch DATA_DIR in the telnet module (it imports its own reference)
    import src.sip.telnet_client as telnet_mod
    monkeypatch.setattr(telnet_mod, "DATA_DIR", data_dir)

    return data_dir


@pytest.fixture()
def mock_pjsua(monkeypatch):
    """Mock the pjsua singleton so no subprocess is started."""
    from src.sip import pjsua_manager

    mock = MagicMock()
    mock.running = False
    mock.pid = None
    mock.start = AsyncMock()
    mock.stop = AsyncMock()
    mock.restart = AsyncMock()
    monkeypatch.setattr(pjsua_manager, "pjsua", mock)
    return mock


@pytest.fixture()
def mock_system(monkeypatch):
    """Mock system-level helpers that touch /proc, /sys, systemctl, etc."""
    import src.config.system as system_mod

    monkeypatch.setattr(system_mod, "apply_performance_governor", lambda: None)
    monkeypatch.setattr(system_mod, "apply_network_config", lambda: None)
    monkeypatch.setattr(system_mod, "apply_wifi_config", lambda: None)
    monkeypatch.setattr(system_mod, "apply_8021x_config", lambda: None)
    monkeypatch.setattr(system_mod, "apply_timezone", lambda: None)
    monkeypatch.setattr(system_mod, "apply_ntp_config", lambda: None)
    monkeypatch.setattr(system_mod, "apply_ptp_config", lambda: None)
    monkeypatch.setattr(system_mod, "apply_aes67_config", lambda: None)
    monkeypatch.setattr(system_mod, "apply_boot_config", lambda: None)
    monkeypatch.setattr(system_mod, "factory_reset", lambda: None)


@pytest.fixture()
def mock_audio(monkeypatch):
    """Mock ALSA/audio helpers so tests don't need real hardware."""
    import src.audio.mixer as mixer_mod
    import src.audio.devices as devices_mod
    import src.audio.aes67 as aes67_mod

    monkeypatch.setattr(mixer_mod, "get_volume", lambda control="Master": 75)
    monkeypatch.setattr(mixer_mod, "discover_mixers", lambda: {
        "capture_stereo": False,
        "playback_stereo": False,
        "capture_mixers": [],
        "playback_mixers": [],
        "hifi_xlr": [],
    })
    monkeypatch.setattr(mixer_mod, "list_devices", lambda: {"playback": "", "capture": ""})
    monkeypatch.setattr(devices_mod, "discover_devices", lambda: [])
    monkeypatch.setattr(aes67_mod, "has_aes67", lambda: False)
    monkeypatch.setattr(aes67_mod, "get_ptp_status", AsyncMock(return_value={}))
    monkeypatch.setattr(aes67_mod, "get_sources", AsyncMock(return_value=[]))
    monkeypatch.setattr(aes67_mod, "get_remote_sources", AsyncMock(return_value=[]))
    monkeypatch.setattr(aes67_mod, "get_sinks", AsyncMock(return_value=[]))


@pytest.fixture()
def client(mock_pjsua, mock_system, mock_audio):
    """FastAPI TestClient with all external dependencies mocked."""
    from unittest.mock import patch

    # Patch connect_telnet so lifespan doesn't try to open a real connection
    with patch("src.api.main.connect_telnet", new_callable=AsyncMock):
        from src.api.main import app
        from starlette.testclient import TestClient

        with TestClient(app) as c:
            yield c
