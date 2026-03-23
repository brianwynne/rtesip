"""Telnet client for pjsua CLI — parses call state, registration, errors.

Connects to pjsua's telnet CLI and translates output into structured events.
"""

import asyncio
import json
import logging
import re
from typing import Callable, Optional

from src.config.settings import DATA_DIR, get_section

logger = logging.getLogger(__name__)


class CallState:
    IDLE = "idle"
    CALLING = "calling"
    RINGING = "ringing"
    INCOMING = "incoming"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class PjsuaTelnet:
    """Async telnet client for pjsua CLI control."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9090):
        self.host = host
        self.port = port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._read_task: Optional[asyncio.Task] = None

        # Read buffer for line splitting
        self._buffer = ""

        # State
        self.call_state = CallState.IDLE
        self.current_contact: Optional[str] = None
        self.active_accounts: dict[str, bool] = {}
        self.sip_ready = False

        # Event callback
        self._on_event: Optional[Callable] = None

    @property
    def connected(self) -> bool:
        return self._connected

    def on_event(self, callback: Callable) -> None:
        """Register callback for events: callback(event_type, data_dict)"""
        self._on_event = callback

    async def connect(self) -> bool:
        """Connect to pjsua telnet CLI."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=3,
            )
            self._connected = True
            logger.info("Connected to pjsua CLI at %s:%d", self.host, self.port)

            # Initial queries on connect
            await self.send("acc show")
            await self.send("call list")

            # Start reading
            self._read_task = asyncio.create_task(self._read_loop())
            return True
        except (ConnectionRefusedError, asyncio.TimeoutError, OSError) as e:
            logger.warning("Cannot connect to pjsua CLI: %s", e)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        if self._read_task:
            self._read_task.cancel()
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        self._connected = False

    async def send(self, command: str) -> None:
        """Send command to pjsua CLI."""
        if not self._connected or not self._writer:
            logger.warning("Not connected, cannot send: %s", command)
            return
        try:
            self._writer.write(f"{command}\r\n".encode())
            await self._writer.drain()
            logger.debug("Sent: %s", command)
        except Exception as e:
            logger.error("Send failed: %s", e)
            self._connected = False

    # --- Call control commands ---

    async def make_call(self, uri: str, account_id: int = 0) -> None:
        await self.send(f"acc next {account_id}")
        await self.send(f"call new sip:{uri}")

    async def answer(self) -> None:
        await self.send("call answer 200")

    async def hangup(self) -> None:
        await self.send("call hangup")

    async def reject(self) -> None:
        await self.send("call answer 486")

    async def set_volume(self, capture: float, playback: float) -> None:
        """Set pjsua software mixer levels (capture and playback)."""
        await self.send(f"V {capture:.2f} {playback:.2f}")

    async def play_tone(self, tone_id: int) -> None:
        """Play wav file: 0=ready, 1=error."""
        await self.send(f"cc {tone_id} 0")

    # --- Output parsing ---

    async def _read_loop(self) -> None:
        """Read and parse pjsua telnet output."""
        try:
            while self._connected:
                data = await self._reader.read(16384)
                if not data:
                    logger.warning("pjsua CLI connection closed")
                    self._connected = False
                    await self._emit("backend_disconnected", {})
                    break
                self._buffer += data.decode("utf-8", errors="replace")
                # Process only complete lines; keep partial trailing data in buffer
                while "\n" in self._buffer:
                    line, self._buffer = self._buffer.split("\n", 1)
                    self._parse_line(line.strip())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Read loop error: %s", e)
            self._connected = False

    def _parse_line(self, data: str) -> None:
        """Parse a single line of pjsua telnet output into a structured event."""
        if not data or data == "rtesip>":
            return

        # Call state: CONFIRMED
        if re.search(r"Call [0-9] state changed to CONFIRMED$", data):
            asyncio.create_task(self.send("call list"))

        elif m := re.search(r"Current call id\=[0-9] to (.+) \[CONFIRMED\]$", data):
            self.call_state = CallState.CONNECTED
            self._emit_sync("connected", {"destination": self.current_contact})

        # Call state: DISCONNECTED
        elif m := re.search(r"\[DISCONNCTD\] t\: ([^;]+)", data):
            self.call_state = CallState.IDLE
            self._emit_sync("ended", {"destination": m.group(1)})
            self.current_contact = None

        # Incoming call
        elif (m := re.search(r"From\: (.+)", data)) or \
             (m := re.search(r"Current call id\=[0-9] to (.+) \[INCOMING\]$", data)):
            self.call_state = CallState.INCOMING
            contact = self._resolve_contact(m.group(1))
            self.current_contact = contact
            self._emit_sync("incoming", {"destination": contact})

            # 4. Auto answer — if enabled, automatically answer incoming calls
            audio = get_section("audio")
            if audio.get("auto_answer", False):
                logger.info("Auto-answer enabled, answering incoming call from %s", contact)
                asyncio.create_task(self.answer())

        # Call state: CALLING
        elif re.search(r"Call [0-9] state changed to CALLING$", data) or \
             re.search(r"Current call id\=[0-9] to .+ \[CALLING\]$", data):
            self.call_state = CallState.CALLING
            self._emit_sync("calling", {"destination": self.current_contact})

        # Call state: RINGING (180)
        elif re.search(r"Call [0-9] state changed to EARLY \(180 Ringing\)$", data) or \
             re.search(r"Current call id\=[0-9] to .+ \[EARLY\]$", data):
            self.call_state = CallState.RINGING
            self._emit_sync("ringing", {"destination": self.current_contact or ""})

        # Registration status
        elif (m := re.search(r"\[ [0-9]\] sip\:([^\:]+)\: ([0-9]{3})\/[A-z\s]+ \(expires\=(-?[0-9]+)\)", data)) or \
             (m := re.search(r"sip\:([^\:]+)\: registration.+status\=([0-9]{1,3}) \([A-z]+\)", data)):
            account_id = m.group(1)
            status = int(m.group(2))
            self.active_accounts[account_id] = (status == 200)

            if status == 200:
                if not self.sip_ready:
                    self.sip_ready = True
                    asyncio.create_task(self.play_tone(1))
                self._emit_sync("account", {"id": account_id, "status": status, "registered": True})
            elif status > 200:
                if not self.sip_ready:
                    asyncio.create_task(self.play_tone(2))
                self._emit_sync("account", {"id": account_id, "status": status, "registered": False})

        # Audio device error
        elif "PJMEDIA_EAUD_SYSERR" in data:
            self._emit_sync("audio_error", {"error": "device_error"})

        # STUN/network errors
        elif any(err in data for err in ["PJNATH_ESTUNTIMEDOUT", "Error sending STUN request", "PJ_ERESOLVE"]):
            if "not nominated" not in data and "REGISTER" not in data and "registration" not in data:
                self._emit_sync("network_error", {"error": data})

        # Connection errors
        elif ("Connection timed out" in data or "Connection refused" in data) and not self.current_contact:
            self._emit_sync("connection_error", {"error": data})

        # SIP error reason
        elif m := re.search(r"\[reason\=([0-9]{3}) \((.+)\)\]$", data):
            self._emit_sync("reason", {"code": int(m.group(1)), "verbose": m.group(2)})

        # Debug/other output
        else:
            clean = data.replace("\x07", "")
            if clean:
                self._emit_sync("debug", {"data": clean})

    def _resolve_contact(self, raw: str) -> str:
        """Parse SIP From header into display name."""
        raw = raw.strip()
        m = re.match(r'("(.*)")?\s*<?sip:([^>]+)>?', raw)
        if m and m.group(3):
            address = m.group(3)
            display = m.group(2) or ""
            # Strip phone number prefix for PSTN
            if address.startswith("+") and "@" in address:
                address = address.split("@")[0]
            # Contact list lookup
            contacts_file = DATA_DIR / "contacts.json"
            if contacts_file.exists():
                try:
                    contacts = json.loads(contacts_file.read_text())
                    for contact in contacts:
                        if contact.get("address") == address or contact.get("uri") == address:
                            return f"{contact['name']} <sip:{address}>"
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Failed to load contacts: %s", e)
            if display:
                return f"{display} <sip:{address}>"
            return address
        return raw

    def _emit_sync(self, event: str, data: dict) -> None:
        if self._on_event:
            asyncio.create_task(self._on_event(event, data))

    async def _emit(self, event: str, data: dict) -> None:
        if self._on_event:
            await self._on_event(event, data)
