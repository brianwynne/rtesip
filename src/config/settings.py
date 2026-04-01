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
        "codecs": ["opus/48000/2", "G722/16000/1"],
        "log_level": 3,
    },
    "audio": {
        "channels": 1,
        "bitrate": 64000,
        "ec_tail": 200,
        "opus_complexity": 7,
        "opus_cbr": False,
        "opus_fec": False,
        "opus_packet_loss": 10,
        "opus_frame_duration": 20,
        # Legacy device/routing fields (kept for backward compat)
        "input": "USB",
        "output": "USB",
        "input_routing": "lr",
        "output_routing": "lr",
        # Per-channel device and channel selection
        "input_left_device": "USB",
        "input_left_channel": 0,
        "input_right_device": "USB",
        "input_right_channel": 1,
        "output_left_device": "USB",
        "output_left_channel": 0,
        "output_right_device": "USB",
        "output_right_channel": 1,
        "capture_latency": 10,
        "playback_latency": 10,
        "jitter_buffer": 360,
        "capture_volume": 40,
        "playback_volume": 40,
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


_ROUTING_TO_CHANNELS = {
    "lr": (0, 1),
    "ll": (0, 0),
    "rr": (1, 1),
    "rl": (1, 0),
    "mono": (-1, -1),  # -1 = mix all channels
}


def _migrate_audio_routing(config: dict) -> bool:
    """Migrate old input/output + routing fields to per-channel model.

    Returns True if migration was applied (caller should save).
    """
    audio = config.get("audio", {})

    # Already migrated if any per-channel device is set to a non-default value,
    # OR if old routing fields are absent
    if audio.get("input_routing") is None:
        return False
    # Check if per-channel fields were explicitly saved before (not just defaults)
    # by looking for the _migrated sentinel
    if audio.get("_routing_migrated"):
        return False

    input_dev = audio.get("input", "USB")
    output_dev = audio.get("output", "USB")
    in_route = audio.get("input_routing", "lr")
    out_route = audio.get("output_routing", "lr")

    in_l, in_r = _ROUTING_TO_CHANNELS.get(in_route, (0, 1))
    out_l, out_r = _ROUTING_TO_CHANNELS.get(out_route, (0, 1))

    audio["input_left_device"] = input_dev
    audio["input_left_channel"] = in_l
    audio["input_right_device"] = input_dev
    audio["input_right_channel"] = in_r
    audio["output_left_device"] = output_dev
    audio["output_left_channel"] = out_l
    audio["output_right_device"] = output_dev
    audio["output_right_channel"] = out_r
    audio["_routing_migrated"] = True

    return True


def _config_path() -> Path:
    return DATA_DIR / "config.json"


def load() -> dict[str, Any]:
    """Load config, merging saved values over defaults."""
    path = _config_path()
    needs_save = False
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
            needs_save = _migrate_audio_routing(merged)
        else:
            merged = {k: dict(v) for k, v in DEFAULTS.items()}
    # Save outside the lock to avoid deadlock (save() acquires _config_lock)
    if needs_save:
        save(merged)
    return merged


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
