"""Configuration management — JSON file backed, no database.

Single config.json with sections, plus separate contacts.json.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_DIR = Path("/etc/rtesip")
DATA_DIR = Path("/var/lib/rtesip")

_config_lock = threading.Lock()

DEFAULTS: dict[str, dict] = {
    "base": {
        "product_name": "rtesip",
        "product_code": "",
        "unit_description": "",
        "serial_number": "",
        "language": "english",
    },
    "sip": {
        "accounts": [],
        # Legacy single-account fields (used if accounts list is empty)
        "username": "",
        "password": "",
        "registrar": "",
        "realm": "",
        "proxy": "",
        "proxy2": "",
        "transport": "tls",
        "keying": 2,  # 0=none, 1=SDES, 2=SDES mandatory
        "reg_timeout": 600,
        "stun": "stun.l.google.com:19302",
        "stun2": "turn.rtegroup.ie",
        "codecs": ["opus/48000/2", "L16/48000/1", "G722/16000/1", "PCMA/8000/1", "PCMU/8000/1"],
        "log_level": 3,
    },
    "audio": {
        "channels": 1,
        "bitrate": 64000,
        "input": "USB",
        "output": "USB",
        "input_routing": "lr",
        "output_routing": "lr",
        "capture_latency": 10,
        "playback_latency": 10,
        "period_size": 5,
        "capture_volume": 100,
        "playback_volume": 100,
        "auto_answer": False,
        "mic_monitor": False,
        "hardware_mixer": False,
        "phantom_power": False,
        "wifi_mode": False,
    },
    "display": {
        "mode": "none",  # none | 7inch | 3inch
        "type": "7official",  # 7official | 35adafruit | 35generic
        "rotation": 0,  # 0 or 1
        "brightness": 255,
        "screensaver_timeout": 30,
    },
    "network": {
        "mode": "dhcp",  # dhcp | static
        "hostname": "rtesip",
        "address": "",
        "netmask": "",
        "gateway": "",
        "dns1": "",
        "dns2": "",
        "time_servers": "0.pool.ntp.org\n1.pool.ntp.org\n2.pool.ntp.org\n3.pool.ntp.org",
    },
    "wifi": {
        "enabled": False,
        "ssid": "",
        "psk": "",
        "interface": "wlan0",
        "country": "ie",
        "enable_8021x": False,
        "8021x_user": "",
        "8021x_password": "",
        "8021x_peaplabel1": False,
    },
    "aes67": {
        "enabled": False,
        "ptp_clock": False,
    },
    "security": {
        "firewall_enabled": True,
        "trusted_networks": "192.168.0.0/16\n172.16.0.0/12\n10.0.0.0/8",
        "gui_password_hash": "2866f742b67e89b6772a01b5f31e3aa1ed9b39e28b312455a98a7f2ae9bb6a3b",
    },
    "system": {
        "timezone": "Europe/Dublin",
        "hifi_berry": "none",  # none | dacplusadcpro | etc.
        "performance_governor": True,
    },
}


def _config_path() -> Path:
    return DATA_DIR / "config.json"


def load() -> dict[str, Any]:
    """Load config, merging saved values over defaults."""
    path = _config_path()
    with _config_lock:
        if path.exists():
            try:
                with open(path) as f:
                    saved = json.load(f)
            except json.JSONDecodeError as e:
                logger.error("Corrupt config file %s: %s — falling back to defaults", path, e)
                corrupt = path.with_suffix(".corrupt")
                try:
                    path.rename(corrupt)
                    logger.info("Renamed corrupt config to %s", corrupt)
                except OSError as rename_err:
                    logger.error("Failed to rename corrupt config: %s", rename_err)
                return {k: dict(v) for k, v in DEFAULTS.items()}
            # Merge defaults for any missing keys
            merged = {}
            for section, defaults in DEFAULTS.items():
                merged[section] = {**defaults, **(saved.get(section, {}))}
            return merged
        return {k: dict(v) for k, v in DEFAULTS.items()}


def save(config: dict[str, Any]) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with _config_lock:
        with open(tmp_path, "w") as f:
            json.dump(config, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)


def get_section(section: str) -> dict[str, Any]:
    return load().get(section, {})


def update_section(section: str, values: dict[str, Any]) -> dict[str, Any]:
    config = load()
    if section in config:
        config[section].update(values)
    else:
        config[section] = values
    save(config)
    return config[section]


def get_hardware_info() -> dict:
    """Get RPi CPU serial and model from /proc/cpuinfo."""
    info = {"serial": "", "model": ""}
    try:
        cpuinfo = Path("/proc/cpuinfo").read_text()
        for line in cpuinfo.splitlines():
            if line.startswith("Serial"):
                info["serial"] = line.split(":")[1].strip()
            elif line.startswith("Model"):
                info["model"] = line.split(":")[1].strip()
    except Exception as e:
        logger.warning("Failed to read hardware info: %s", e)
    return info
