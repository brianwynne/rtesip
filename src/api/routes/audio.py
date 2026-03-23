"""Audio control endpoints — volume, devices, AES67."""

from fastapi import APIRouter, Depends

from src.api.auth import require_api_key
from src.audio.mixer import get_volume, discover_mixers, list_devices, toggle_phantom_power
from src.audio.devices import discover_devices
from src.audio.aes67 import (
    get_ptp_status, get_sources, get_remote_sources, get_sinks,
    update_source, update_sink, has_aes67,
)
from src.config.settings import get_section, update_section

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/volume")
async def get_vol():
    return {"input": get_volume("Capture"), "output": get_volume("Master")}


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

    # Restart pjsua to apply device/routing/codec changes
    from src.sip.pjsua_manager import pjsua
    await pjsua.restart()
    return result


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
