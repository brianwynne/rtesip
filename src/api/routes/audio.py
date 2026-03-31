"""Audio control endpoints — volume, devices, AES67."""

import logging
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends

from src.api.auth import require_api_key
from src.audio.mixer import get_volume, discover_mixers, list_devices, toggle_phantom_power
from src.audio.devices import discover_devices

logger = logging.getLogger(__name__)
from src.audio.aes67 import (
    get_ptp_status, get_sources, get_remote_sources, get_sinks,
    update_source, update_sink, has_aes67,
)
from src.config.settings import get_section, update_section

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/volume")
async def get_vol():
    return {"input": get_volume("Capture"), "output": get_volume("Master")}


@router.get("/detected-devices")
async def detected_devices():
    """Return detected audio hardware with channel counts."""
    devices = []
    try:
        cards = Path("/proc/asound/cards").read_text()
        for line in cards.splitlines():
            line = line.strip()
            if not line or line.startswith(" "):
                continue
            parts = line.split()
            if not parts[0].isdigit():
                continue
            card_num = int(parts[0])
            card_id = parts[1].strip("[]")
            # Get full name
            name = line.split(" - ", 1)[1] if " - " in line else card_id

            # Get channel counts
            cap_ch = 0
            play_ch = 0
            try:
                r = subprocess.run(
                    ["arecord", "--dump-hw-params", "-D", f"hw:{card_num},0", "-d", "0"],
                    capture_output=True, text=True, timeout=3
                )
                for l in r.stderr.splitlines():
                    if "CHANNELS:" in l:
                        cap_ch = int(l.split(":")[1].strip())
            except Exception:
                pass
            try:
                r = subprocess.run(
                    ["aplay", "--dump-hw-params", "-D", f"hw:{card_num},0", "-d", "0", "/dev/zero"],
                    capture_output=True, text=True, timeout=3
                )
                for l in r.stderr.splitlines():
                    if "CHANNELS:" in l:
                        play_ch = int(l.split(":")[1].strip())
            except Exception:
                pass

            is_usb = Path(f"/proc/asound/card{card_num}/usbid").exists()
            devices.append({
                "card": card_num,
                "id": card_id,
                "name": name,
                "usb": is_usb,
                "capture_channels": cap_ch,
                "playback_channels": play_ch,
            })
    except Exception as e:
        logger.warning("Failed to detect audio devices: %s", e)
    return {"devices": devices}


@router.get("/devices")
async def devices():
    return {"devices": [d.__dict__ for d in discover_devices()]}


@router.get("/mixers")
async def mixers():
    m = discover_mixers()
    return {
        "capture_stereo": m["capture_stereo"],
        "playback_stereo": m["playback_stereo"],
        "capture_mixers": len(m["capture_mixers"]),
        "playback_mixers": len(m["playback_mixers"]),
        "hifi_xlr": len(m["hifi_xlr"]),
    }


@router.get("/settings")
async def audio_settings():
    return get_section("audio")


@router.put("/settings")
async def update_audio(settings: dict):
    old_audio = get_section("audio")
    result = update_section("audio", settings)

    # Apply phantom power change immediately if it changed
    if "phantom_power" in settings and settings["phantom_power"] != old_audio.get("phantom_power"):
        mixers = discover_mixers()
        hifi_xlr_cards = mixers.get("hifi_xlr", [])
        if hifi_xlr_cards:
            toggle_phantom_power(hifi_xlr_cards, settings["phantom_power"])

    # Apply volume changes to mixer state
    from src.api.ws import mixer_state, telnet
    if "capture_volume" in settings or "playback_volume" in settings:
        if "capture_volume" in settings:
            mixer_state.capture_left = settings["capture_volume"]
            mixer_state.capture_right = settings["capture_volume"]
        if "playback_volume" in settings:
            mixer_state.playback_left = settings["playback_volume"]
            mixer_state.playback_right = settings["playback_volume"]
        # Send to pjsua if using software mixer
        if not mixer_state.hardware_mixer and telnet.connected:
            capture = mixer_state.capture_left / 100
            playback = mixer_state.playback_left / 100
            await telnet.set_volume(capture, playback)

    # Apply hardware mixer change
    if "hardware_mixer" in settings:
        mixer_state.hardware_mixer = settings["hardware_mixer"]

    # Apply mic monitor change
    if "mic_monitor" in settings and telnet.connected:
        if settings["mic_monitor"]:
            await telnet.send("cc 0 0")
        # Note: disconnecting mic monitor requires pjsua restart

    # Update ALSA config if any channel routing fields changed
    _channel_fields = {
        "input_left_device", "input_left_channel",
        "input_right_device", "input_right_channel",
        "output_left_device", "output_left_channel",
        "output_right_device", "output_right_channel",
        "input_routing", "output_routing",
    }
    if _channel_fields & settings.keys():
        generate_asound_conf()

    # Restart pjsua to apply device/routing/codec changes
    from src.sip.pjsua_manager import pjsua
    await pjsua.restart()
    return result


# ---------------------------------------------------------------------------
# ALSA asound.conf generation
# ---------------------------------------------------------------------------

ASOUND_CONF = Path("/etc/asound.conf")


def _resolve_card_number(device_str: str) -> int | None:
    """Resolve a device string ('USB' or 'plughw:CARD=xxx,DEV=0') to ALSA card number."""
    try:
        cards_text = Path("/proc/asound/cards").read_text()
    except Exception:
        return None

    for line in cards_text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if not parts[0].isdigit():
            continue
        card_num = int(parts[0])
        card_id = parts[1].strip("[]")

        if device_str == "USB":
            if Path(f"/proc/asound/card{card_num}/usbid").exists():
                return card_num
        elif card_id in device_str:
            return card_num

    return None


def _pcm_section(direction: str, left_dev: str, left_ch: int,
                 right_dev: str, right_ch: int, channels: int) -> str:
    """Generate ALSA PCM config for one direction (capture or playback).

    Returns ALSA config text defining rtesip_cap or rtesip_play.
    """
    pcm_name = "rtesip_cap" if direction == "capture" else "rtesip_play"
    slave_type = "dsnoop" if direction == "capture" else "dmix"

    left_card = _resolve_card_number(left_dev)
    right_card = _resolve_card_number(right_dev)

    if left_card is None:
        left_card = 0
    if right_card is None:
        right_card = left_card

    lines = []

    # Mono mode — single channel
    if channels == 1:
        if left_ch == -1:
            # Mix all channels to mono
            lines.append(f"pcm.{pcm_name} {{")
            lines.append(f"    type route")
            lines.append(f'    slave.pcm "{slave_type}:{left_card},0"')
            lines.append(f"    slave.channels 2")
            lines.append(f"    ttable.0.0 0.5")
            lines.append(f"    ttable.0.1 0.5")
            lines.append(f"}}")
        else:
            # Single channel from device
            lines.append(f"pcm.{pcm_name} {{")
            lines.append(f"    type route")
            lines.append(f'    slave.pcm "{slave_type}:{left_card},0"')
            lines.append(f"    slave.channels 2")
            lines.append(f"    ttable.0.{left_ch} 1.0")
            lines.append(f"}}")
        return "\n".join(lines)

    # Stereo mode
    same_device = (left_card == right_card)

    if same_device:
        if left_ch == -1 or right_ch == -1:
            # Mix all to mono on both channels
            lines.append(f"pcm.{pcm_name} {{")
            lines.append(f"    type route")
            lines.append(f'    slave.pcm "{slave_type}:{left_card},0"')
            lines.append(f"    slave.channels 2")
            lines.append(f"    ttable.0.0 0.5")
            lines.append(f"    ttable.0.1 0.5")
            lines.append(f"    ttable.1.0 0.5")
            lines.append(f"    ttable.1.1 0.5")
            lines.append(f"}}")
        elif left_ch == 0 and right_ch == 1:
            # Standard L/R — simple plug
            lines.append(f"pcm.{pcm_name} {{")
            lines.append(f"    type plug")
            lines.append(f"    slave {{")
            lines.append(f'        pcm "{slave_type}:{left_card},0"')
            lines.append(f"        rate 48000")
            lines.append(f"    }}")
            lines.append(f"}}")
        else:
            # Remapped channels on same device
            lines.append(f"pcm.{pcm_name} {{")
            lines.append(f"    type route")
            lines.append(f'    slave.pcm "{slave_type}:{left_card},0"')
            lines.append(f"    slave.channels 2")
            lines.append(f"    ttable.0.{left_ch} 1.0")
            lines.append(f"    ttable.1.{right_ch} 1.0")
            lines.append(f"}}")
    else:
        # Cross-device — use ALSA multi plugin
        multi_name = f"rtesip_multi_{pcm_name.split('_')[1]}"
        lines.append(f"pcm.{multi_name} {{")
        lines.append(f"    type multi")
        lines.append(f"    slaves.a.pcm \"{slave_type}:{left_card},0\"")
        lines.append(f"    slaves.a.channels 2")
        lines.append(f"    slaves.b.pcm \"{slave_type}:{right_card},0\"")
        lines.append(f"    slaves.b.channels 2")
        lines.append(f"    bindings.0.slave a")
        lines.append(f"    bindings.0.channel {max(left_ch, 0)}")
        lines.append(f"    bindings.1.slave b")
        lines.append(f"    bindings.1.channel {max(right_ch, 0)}")
        lines.append(f"}}")
        lines.append(f"")
        lines.append(f"pcm.{pcm_name} {{")
        lines.append(f"    type plug")
        lines.append(f'    slave.pcm "{multi_name}"')
        lines.append(f"}}")

    return "\n".join(lines)


def generate_asound_conf():
    """Generate /etc/asound.conf from per-channel audio settings."""
    audio = get_section("audio")
    channels = audio.get("channels", 1)

    cap_section = _pcm_section(
        "capture",
        audio.get("input_left_device", "USB"),
        audio.get("input_left_channel", 0),
        audio.get("input_right_device", "USB"),
        audio.get("input_right_channel", 1),
        channels,
    )
    play_section = _pcm_section(
        "playback",
        audio.get("output_left_device", "USB"),
        audio.get("output_left_channel", 0),
        audio.get("output_right_device", "USB"),
        audio.get("output_right_channel", 1),
        channels,
    )

    # Determine ctl device (use playback left card)
    ctl_card = _resolve_card_number(audio.get("output_left_device", "USB"))
    if ctl_card is None:
        ctl_card = 0

    conf = f"""# Auto-generated by rtesip — per-channel audio routing

{cap_section}

{play_section}

pcm.!default {{
    type asym
    playback.pcm rtesip_play
    capture.pcm rtesip_cap
}}

ctl.!default {{
    type hw
    card {ctl_card}
}}
"""

    try:
        ASOUND_CONF.write_text(conf)
        logger.info("Generated %s", ASOUND_CONF)
    except OSError as e:
        logger.warning("Cannot write %s: %s", ASOUND_CONF, e)


# --- AES67 ---

@router.get("/aes67/status")
async def aes67_status():
    return {
        "available": has_aes67(),
        "ptp": await get_ptp_status(),
    }


@router.get("/aes67/sources")
async def aes67_sources():
    return {"local": await get_sources(), "remote": await get_remote_sources()}


@router.get("/aes67/sinks")
async def aes67_sinks():
    return {"sinks": await get_sinks()}


@router.put("/aes67/source")
async def aes67_update_source(settings: dict):
    return await update_source(settings)


@router.put("/aes67/sink")
async def aes67_update_sink(params: dict):
    remote = await get_remote_sources()
    result = await update_sink(
        params.get("source_id", ""),
        remote,
        params.get("channel_map", [0, 1]),
    )
    if result:
        return result
    return {"error": "Source not found"}
