"""WebSocket endpoint — real-time call state, meters, and control.

Uses challenge-response auth with SHA256.
"""

import asyncio
import hashlib
import ipaddress
import json
import logging
import secrets
import subprocess
from typing import Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.config.settings import get_section, DATA_DIR
from src.sip.telnet_client import PjsuaTelnet
from src.audio.mixer import MixerState
from src.audio.meters import audio_meter  # noqa: F401 — kept for API compat

logger = logging.getLogger(__name__)
router = APIRouter()

clients: Set[WebSocket] = set()
authed_clients: Set[WebSocket] = set()
challenges: dict[WebSocket, str] = {}

# Shared state
telnet: PjsuaTelnet = PjsuaTelnet()
mixer_state = MixerState()


async def broadcast(event: str, data: dict, authed_only: bool = True) -> None:
    """Send event to all connected WebSocket clients."""
    global clients, authed_clients
    message = json.dumps({"event": event, **data})
    target = authed_clients if authed_only else clients
    disconnected = set()
    for ws in list(target):
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    clients -= disconnected
    authed_clients -= disconnected


_PRIVATE_NETS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)


def _is_trusted(ip: str) -> bool:
    """Check if IP is on a private/LAN network."""
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in _PRIVATE_NETS)
    except ValueError:
        return False


async def _send_initial_state(ws: WebSocket) -> None:
    """Send initial state snapshot to a newly authenticated client."""
    await ws.send_text(json.dumps({
        "event": "state",
        "call_state": telnet.call_state,
        "current_contact": telnet.current_contact,
        "accounts": {k: v for k, v in telnet.active_accounts.items()},
        "sip_ready": telnet.sip_ready,
        "server_reachable": telnet.server_reachable,
    }))
    await ws.send_text(json.dumps({
        "event": "levels",
        "cl": mixer_state.capture_left,
        "cr": mixer_state.capture_right,
        "clink": mixer_state.capture_linked,
        "pl": mixer_state.playback_left,
        "pr": mixer_state.playback_right,
        "plink": mixer_state.playback_linked,
    }))


async def on_pjsua_event(event: str, data: dict) -> None:
    """Handle events from pjsua telnet — broadcast to WebSocket clients."""
    await broadcast(event, data)


async def start_meters() -> None:
    """Metering disabled."""
    pass


async def stop_meters() -> None:
    pass


async def connect_telnet() -> None:
    """Connect to pjsua telnet CLI with retry and reconnection on disconnect."""
    telnet.on_event(on_pjsua_event)
    while True:
        if await telnet.connect():
            # Apply initial audio state from config on each connect
            await _apply_initial_audio_state()
            # Wait for the read task to finish (i.e. disconnection)
            if telnet._read_task:
                await telnet._read_task
            logger.info("pjsua CLI disconnected, reconnecting...")
        else:
            logger.info("Waiting for pjsua CLI...")
        await asyncio.sleep(2)


async def _apply_initial_audio_state() -> None:
    """Apply audio config to mixer state and pjsua on telnet connect."""
    audio = get_section("audio")

    # 3. Volume at startup — capture and playback
    capture_vol = audio.get("capture_volume", 25)
    playback_vol = audio.get("playback_volume", 25)
    mixer_state.capture_left = capture_vol
    mixer_state.capture_right = capture_vol
    mixer_state.playback_left = playback_vol
    mixer_state.playback_right = playback_vol

    # 6. Hardware mixer flag
    mixer_state.hardware_mixer = audio.get("hardware_mixer", False)

    # Send initial volume to pjsua via telnet
    # pjsua V command: 1.0 = unity gain, >1.0 = amplify. Scale fader 0-100 to 0.0-4.0x
    if not mixer_state.hardware_mixer:
        capture = mixer_state.capture_left / 100 * 4.0
        playback = mixer_state.playback_left / 100 * 4.0
        await telnet.set_volume(capture, playback)

    # 5. Mic monitor — connect capture to playback port in pjsua conference bridge
    if audio.get("mic_monitor", False):
        # cc 0 0 connects conf port 0 (capture) to conf port 0 (playback)
        await telnet.send("cc 0 0")
        logger.info("Mic monitor enabled — connected capture to playback")

    logger.info(
        "Initial audio state applied: capture=%d playback=%d hw_mixer=%s mic_monitor=%s",
        capture_vol, playback_vol, mixer_state.hardware_mixer, audio.get("mic_monitor", False),
    )


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    logger.info("WebSocket client connected (%d total)", len(clients))

    try:
        while True:
            text = await ws.receive_text()
            msg = json.loads(text)
            command = msg.get("command") or msg.get("action", "")
            # --- Auth (challenge-response with SHA256) ---
            # TODO: Add rate limiting for production — limit auth attempts per IP
            # to prevent brute-force attacks on the challenge-response flow.
            if ws not in authed_clients:
                if command == "authRequest":
                    # Auto-auth for LAN/trusted clients
                    client_ip = ws.client.host if ws.client else ""
                    if _is_trusted(client_ip):
                        authed_clients.add(ws)
                        await _send_initial_state(ws)
                        continue
                    challenge = secrets.token_hex(16)
                    challenges[ws] = challenge
                    await ws.send_text(json.dumps({"event": "challenge", "challenge": challenge}))

                elif command == "challengeResponse":
                    security = get_section("security")
                    pw_hash = security.get("gui_password_hash", "")
                    expected = hashlib.sha256(f"{pw_hash}{challenges.get(ws, '')}".encode()).hexdigest()

                    if msg.get("response") == expected or not pw_hash:
                        authed_clients.add(ws)
                        await _send_initial_state(ws)
                    else:
                        await ws.send_text(json.dumps({"event": "notAuthed"}))
                continue

            # --- Call control ---
            if command == "call":
                address = msg.get("address", "").strip().lower()
                if address:
                    telnet.current_contact = address
                    await telnet.make_call(address)

            elif command == "hangup":
                await telnet.hangup()

            elif command == "answer":
                await telnet.answer()

            elif command == "reject":
                await telnet.reject()

            # --- Volume control ---
            elif command == "vol":
                _handle_volume(msg, "playback")
                await _broadcast_levels()

            elif command == "gain":
                _handle_volume(msg, "capture")
                await _broadcast_levels()

            elif command == "mute":
                _handle_mute(msg)
                await _broadcast_levels()

            # --- Status query ---
            elif command == "status":
                await telnet.send("acc show")
                await telnet.send("call list")

            elif command == "getContacts":
                contacts_file = DATA_DIR / "contacts.json"
                if contacts_file.exists():
                    contacts = json.loads(contacts_file.read_text())
                    await ws.send_text(json.dumps({"event": "contactList", "contacts": contacts}))

            # --- Display control ---
            elif command == "display":
                if msg.get("set") == "off":
                    subprocess.run(["xset", "-display", ":0", "dpms", "force", "off"],
                                   capture_output=True, timeout=5)
                elif msg.get("set") == "on":
                    subprocess.run(["xset", "-display", ":0", "-dpms"],
                                   capture_output=True, timeout=5)

            # --- Direct backend command (debug) ---
            elif command == "backend":
                await telnet.send(msg.get("message", ""))

    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)
        authed_clients.discard(ws)
        challenges.pop(ws, None)
        logger.info("WebSocket client disconnected (%d remaining)", len(clients))


def _handle_volume(msg: dict, channel_type: str) -> None:
    """Handle vol/gain commands."""
    prefix = "playback" if channel_type == "playback" else "capture"
    max_vol = 150 if mixer_state.hardware_mixer else 100
    linked = getattr(mixer_state, f"{prefix}_linked")

    if "channel" in msg:
        ch = msg["channel"]  # 'l' or 'r'
        attr_main = f"{prefix}_{'left' if ch == 'l' else 'right'}"
        attr_other = f"{prefix}_{'right' if ch == 'l' else 'left'}"

        current = getattr(mixer_state, attr_main)
        if "level" in msg:
            # Absolute level from fader drag
            level = max(0, min(int(msg["level"]), max_vol))
            setattr(mixer_state, attr_main, level)
            if linked:
                setattr(mixer_state, attr_other, level)
        elif msg.get("direction") == "up":
            setattr(mixer_state, attr_main, min(current + 10, max_vol))
            if linked:
                setattr(mixer_state, attr_other, min(getattr(mixer_state, attr_other) + 10, max_vol))
        elif msg.get("direction") == "down":
            setattr(mixer_state, attr_main, max(current - 10, 0))
            if linked:
                setattr(mixer_state, attr_other, max(getattr(mixer_state, attr_other) - 10, 0))

    elif "link" in msg:
        if msg["link"]:
            left = getattr(mixer_state, f"{prefix}_left")
            right = getattr(mixer_state, f"{prefix}_right")
            avg = round((left + right) / 20) * 10
            setattr(mixer_state, f"{prefix}_left", avg)
            setattr(mixer_state, f"{prefix}_right", avg)
            setattr(mixer_state, f"{prefix}_linked", True)
        else:
            setattr(mixer_state, f"{prefix}_linked", False)


def _handle_mute(msg: dict) -> None:
    """Handle mute toggle."""
    if msg.get("which") == "vol":
        channels = ["playback_left", "playback_right"]
        bufs = ["playback_left_mute_buf", "playback_right_mute_buf"]
    else:
        channels = ["capture_left", "capture_right"]
        bufs = ["capture_left_mute_buf", "capture_right_mute_buf"]

    if getattr(mixer_state, channels[0]) or getattr(mixer_state, channels[1]):
        # Mute: save current, set to 0
        for ch, buf in zip(channels, bufs):
            setattr(mixer_state, buf, getattr(mixer_state, ch))
            setattr(mixer_state, ch, 0)
    else:
        # Unmute: restore from buffer
        for ch, buf in zip(channels, bufs):
            saved = getattr(mixer_state, buf)
            setattr(mixer_state, ch, saved if saved else 100)


async def _broadcast_levels() -> None:
    """Broadcast volume levels to all connected clients."""
    await broadcast("levels", {
        "cl": mixer_state.capture_left,
        "cr": mixer_state.capture_right,
        "clink": mixer_state.capture_linked,
        "pl": mixer_state.playback_left,
        "pr": mixer_state.playback_right,
        "plink": mixer_state.playback_linked,
    })

    # Send to hardware mixer if enabled
    if mixer_state.hardware_mixer:
        try:
            from src.audio.mixer import discover_mixers, set_mixer_volume
            mixers = discover_mixers()
            set_mixer_volume(
                mixers["capture_mixers"], mixers["capture_amps"],
                mixer_state.capture_left, mixer_state.capture_right,
            )
            set_mixer_volume(
                mixers["playback_mixers"], mixers["playback_amps"],
                mixer_state.playback_left, mixer_state.playback_right,
            )
        except Exception as e:
            logger.warning("Hardware mixer volume update failed: %s", e)
    else:
        # Software mixer via pjsua — scale fader 0-100 to 0.0-4.0x
        capture = mixer_state.capture_left / 100 * 4.0
        playback = mixer_state.playback_left / 100 * 4.0
        await telnet.set_volume(capture, playback)
