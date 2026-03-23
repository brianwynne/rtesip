"""ALSA mixer control — volume, mute, and HiFiBerry XLR support.

- On-demand calls instead of polling daemon
- USB hotplug detection via asyncio
- HiFiBerry XLR phantom power support
"""

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MixerControl:
    name: str
    num: int
    card: int
    direction: str  # 'capture' or 'playback'
    stereo: bool
    muted: bool = False


@dataclass
class MixerState:
    """Volume state — capture/playback levels, mute buffers, and link flags."""
    capture_left: int = 100
    capture_right: int = 100
    capture_left_mute_buf: int = 0
    capture_right_mute_buf: int = 0
    capture_linked: bool = False
    playback_left: int = 100
    playback_right: int = 100
    playback_left_mute_buf: int = 0
    playback_right_mute_buf: int = 0
    playback_linked: bool = False
    hardware_mixer: bool = False


def _amixer(args: list[str], timeout: int = 5) -> str:
    try:
        result = subprocess.run(
            ["amixer"] + args,
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.error("amixer error: %s", result.stderr)
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error("amixer failed: %s", e)
        return ""


def discover_mixers() -> dict:
    """Discover ALSA mixer controls.

    Returns dict with playback_mixers, capture_mixers, playback_amps,
    capture_amps, hifi_xlr cards, and stereo capabilities.
    """
    result = {
        "playback_mixers": [],
        "capture_mixers": [],
        "playback_amps": [],
        "capture_amps": [],
        "hifi_xlr": [],
        "has_preamp": {},
        "capture_stereo": False,
        "playback_stereo": False,
    }

    # Count soundcards
    try:
        aplay_out = subprocess.run(
            ["aplay", "-l"], capture_output=True, text=True, timeout=5
        ).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return result

    max_card = -1
    for line in aplay_out.splitlines():
        import re
        m = re.match(r"^card (\d+):", line)
        if m:
            max_card = max(max_card, int(m.group(1)))

    for card in range(max_card + 1):
        mixer_output = _amixer(["-c", str(card)])
        controls = mixer_output.split("Simple mixer control ")
        pdone = cdone = False

        for ctrl in controls:
            m = re.match(r"'([^']+)',(\d+)", ctrl)
            if not m:
                continue
            name, num = m.group(1), int(m.group(2))
            stereo = "Left" in ctrl and "Right" in ctrl

            # HiFiBerry XLR detection
            if name == "ADC Mic Bias":
                result["hifi_xlr"].append(card)
                _amixer(["-c", str(card), "set", "ADC Mic Bias", "Mic Bias off"])

            # Capture controls
            if "cvolume" in ctrl:
                if not cdone and "matrix" not in name.lower() and "Soft Pre-Amp" not in name:
                    result["capture_mixers"].append(
                        MixerControl(name=name, num=num, card=card, direction="capture", stereo=stereo)
                    )
                    if stereo:
                        result["capture_stereo"] = True
                elif "Soft Pre-Amp" in name:
                    result["capture_amps"].append(
                        MixerControl(name=name, num=num, card=card, direction="capture", stereo=stereo)
                    )
                    result["has_preamp"][card] = True
                if "master" in name.lower():
                    cdone = True

            # Playback controls
            if "pvolume" in ctrl:
                if not pdone and "matrix" not in name.lower() and "Soft Pre-Amp" not in name:
                    result["playback_mixers"].append(
                        MixerControl(name=name, num=num, card=card, direction="playback", stereo=stereo)
                    )
                    if stereo:
                        result["playback_stereo"] = True
                elif "Soft Pre-Amp" in name:
                    result["playback_amps"].append(
                        MixerControl(name=name, num=num, card=card, direction="playback", stereo=stereo)
                    )
                    result["has_preamp"][card] = True
                if "master" in name.lower():
                    pdone = True

    return result


def set_mixer_volume(mixers: list[MixerControl], amps: list[MixerControl],
                     vol_left: int, vol_right: int, force_unmute: bool = False) -> None:
    """Set volume on mixer controls.

    Supports >100% via software pre-amp (softvol).
    """
    l_vol = min(vol_left, 100)
    r_vol = min(vol_right, 100)
    l_amp = (vol_left - 100) * 2 if vol_left > 100 else (0 if vol_left == 0 else 1)
    r_amp = (vol_right - 100) * 2 if vol_right > 100 else (0 if vol_right == 0 else 1)

    for mixer in mixers:
        if mixer.muted or force_unmute:
            mixer.muted = False
            cap_or_unmute = "cap" if mixer.direction == "capture" else "unmute"
            _amixer(["-c", str(mixer.card), "set", f"{mixer.name},{mixer.num}",
                     mixer.direction, cap_or_unmute])
        _amixer(["-c", str(mixer.card), "-M", "set", mixer.name,
                 mixer.direction, f"{l_vol}%,{r_vol}%"])

    for amp in amps:
        _amixer(["-c", str(amp.card), "-M", "set", amp.name,
                 amp.direction, f"{l_amp}%,{r_amp}%"])


def init_hifi_xlr(cards: list[int]) -> None:
    """Initialize HiFiBerry XLR board.

    Sets balanced differential inputs and enables headphone amp via i2c.
    """
    for card in cards:
        _amixer(["-c", str(card), "set", "ADC Left Input", "{VIN1P, VIN1M}[DIFF]"])
        _amixer(["-c", str(card), "set", "ADC Right Input", "{VIN2P, VIN2M}[DIFF]"])
        # Enable headphone amp via i2c
        subprocess.run(["i2cset", "-y", "1", "0x60", "0x01", "0xc0"],
                       capture_output=True, timeout=5)
        subprocess.run(["i2cset", "-y", "1", "0x60", "0x02", "0x20"],
                       capture_output=True, timeout=5)


def toggle_phantom_power(cards: list[int], on: bool) -> None:
    """Toggle 48V phantom power on HiFiBerry XLR board."""
    state = "Mic Bias on" if on else "Mic Bias off"
    for card in cards:
        _amixer(["-c", str(card), "set", "ADC Mic Bias", state])


def get_volume(control: str = "Master") -> int:
    """Get current volume percentage."""
    output = _amixer(["sget", control])
    for line in output.splitlines():
        if "%" in line:
            start = line.index("[") + 1
            end = line.index("%")
            return int(line[start:end])
    return 0


def list_devices() -> dict:
    """List available ALSA playback and capture devices."""
    playback = subprocess.run(
        ["aplay", "-l"], capture_output=True, text=True, timeout=5
    ).stdout
    capture = subprocess.run(
        ["arecord", "-l"], capture_output=True, text=True, timeout=5
    ).stdout
    return {"playback": playback, "capture": capture}
