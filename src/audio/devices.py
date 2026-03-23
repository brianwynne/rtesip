"""Audio device discovery and resolution — enumerates ALSA devices and resolves IDs for pjsua."""

import re
import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AudioDevice:
    num: int
    card_id: str
    card_name: str
    driver: str
    device_type: str  # plughw, hw, etc.
    sub_type: str     # USB, AES67, etc.
    unique_id: str
    has_input: bool
    has_output: bool


def discover_devices() -> list[AudioDevice]:
    """Discover ALSA audio devices from /proc/asound/cards and aplay/arecord."""
    devices = []

    # Get card names from /proc/asound/cards
    card_names = {}
    cards_path = Path("/proc/asound/cards")
    if cards_path.exists():
        for line in cards_path.read_text().splitlines():
            m = re.match(r"\s*(\d+)\s+\[(\w+)\s*\]:\s+(\S+)\s+-\s+(.+)", line)
            if m:
                card_names[m.group(2)] = {
                    "id": m.group(2),
                    "num": m.group(1),
                    "driver": m.group(3).strip(),
                    "name": m.group(4).strip(),
                }

    # Get device list from aplay/arecord
    try:
        play_out = subprocess.run(["aplay", "-l"], capture_output=True, text=True, timeout=5).stdout
        rec_out = subprocess.run(["arecord", "-l"], capture_output=True, text=True, timeout=5).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return devices

    playback_cards = set()
    capture_cards = set()

    for line in play_out.splitlines():
        m = re.match(r"card (\d+):", line)
        if m:
            playback_cards.add(int(m.group(1)))

    for line in rec_out.splitlines():
        m = re.match(r"card (\d+):", line)
        if m:
            capture_cards.add(int(m.group(1)))

    for card_id, info in card_names.items():
        card_num = int(info["num"])
        name = info["name"]

        # Determine sub-type
        sub_type = ""
        if "usb" in name.lower() or "USB" in info["driver"]:
            sub_type = "USB"
        elif "aes67" in name.lower() or "AES67" in card_id:
            sub_type = "AES67"
        elif "hifiberry" in name.lower():
            sub_type = "HiFiBerry"

        # Skip HDMI
        if "hdmi" in name.lower():
            continue

        device = AudioDevice(
            num=card_num,
            card_id=card_id,
            card_name=name,
            driver=info["driver"],
            device_type="plughw",
            sub_type=sub_type,
            unique_id=f"plughw:CARD={card_id},DEV=0",
            has_input=card_num in capture_cards,
            has_output=card_num in playback_cards,
        )
        devices.append(device)

    return devices


def resolve_device(device_id: str, direction: str = "out",
                    device_type: str = "lr") -> Optional[int]:
    """Resolve device identifier to pjsua device number.

    device_id: "USB", or "plughw:CARD=xxx,DEV=0"
    direction: "in" or "out"
    device_type: routing type — "lr" (normal), "ll", "rr", "rl" (channel routing).
                 When not "lr", the ALSA PCM name is prefixed with the routing
                 type (e.g. "ll:CARD=xxx") which selects the corresponding
                 route_XX PCM defined in asound.conf.
    """
    devices = discover_devices()

    def _match(dev: AudioDevice) -> bool:
        if direction == "out":
            return dev.has_output
        return dev.has_input

    def _apply_routing(dev: AudioDevice) -> AudioDevice:
        """Apply routing prefix to device unique_id if not default lr."""
        if device_type and device_type != "lr":
            # Replace the plughw prefix with the routing PCM name
            # e.g. "plughw:CARD=xxx,DEV=0" -> "ll:CARD=xxx,DEV=0"
            dev.unique_id = f"{device_type}:{dev.unique_id.split(':', 1)[1]}" if ':' in dev.unique_id else dev.unique_id
            dev.device_type = device_type
        return dev

    if device_id == "USB":
        for dev in devices:
            if dev.sub_type == "USB" and _match(dev):
                _apply_routing(dev)
                return dev.num
        return None

    # Match by unique ID (check both raw and with routing prefix)
    for dev in devices:
        if dev.unique_id == device_id and _match(dev):
            _apply_routing(dev)
            return dev.num

    # Also match by card_id substring
    for dev in devices:
        if dev.card_id in device_id and _match(dev):
            _apply_routing(dev)
            return dev.num

    return None
