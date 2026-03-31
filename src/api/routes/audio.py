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

    # Update ALSA routing if changed
    if "input_routing" in settings or "output_routing" in settings:
        _update_asound_routing()

    # Update ALSA routing if changed
    if "input_routing" in settings or "output_routing" in settings:
        _update_asound_routing()

    # Restart pjsua to apply device/routing/codec changes
    from src.sip.pjsua_manager import pjsua
    await pjsua.restart()
    return result


def _update_asound_routing():
    """Update /etc/asound.conf default PCM based on routing settings."""
    import re
    audio = get_section("audio")
    in_route = audio.get("input_routing", "lr")
    out_route = audio.get("output_routing", "lr")

    cap_pcm = "usb_cap" if in_route == "lr" else f"cap_{in_route}"
    play_pcm = "usb_play" if out_route == "lr" else f"play_{out_route}"

    asound_path = Path("/etc/asound.conf")
    if not asound_path.exists():
        return

    content = asound_path.read_text()
    # Replace the default PCM section
    new_default = f"""pcm.!default {{
    type asym
    playback.pcm {play_pcm}
    capture.pcm {cap_pcm}
}}"""
    content = re.sub(
        r'pcm\.!default\s*\{[^}]*\}',
        new_default,
        content
    )
    asound_path.write_text(content)
    logger.info("ALSA routing updated: capture=%s playback=%s", cap_pcm, play_pcm)


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
