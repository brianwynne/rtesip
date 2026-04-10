"""Telnet client for pjsua CLI — parses call state, registration, errors.

Connects to pjsua's telnet CLI and translates output into structured events.
Compatible with pjsua/pjsip 2.14.
"""

import asyncio
import json
import logging
import re
import time
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
        self._keepalive_task: Optional[asyncio.Task] = None

        # Read buffer for line splitting
        self._buffer = ""

        # State
        self.call_state = CallState.IDLE
        self.current_contact: Optional[str] = None
        self.active_accounts: dict[str, bool] = {}
        self.sip_ready = False
        self.server_reachable = False
        self.connected_at: Optional[str] = None
        self.current_codec: Optional[str] = None
        self.srtp_active: bool = False
        self.srtp_suite: Optional[str] = None

        # Incoming call multi-line parsing
        self._incoming_pending = False

        # Call quality metrics (from dump_q)
        self.call_quality: dict = {}
        self._quality_poll_task: Optional[asyncio.Task] = None
        self._dump_q_lines: list[str] = []
        self._collecting_dump_q = False
        self._prev_quality: Optional[dict] = None
        self._prev_quality_time: float = 0

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
            import datetime
            self.connected_at = datetime.datetime.now().isoformat()
            logger.info("Connected to pjsua CLI at %s:%d", self.host, self.port)

            # Initial queries on connect
            await self.send("acc show")
            await self.send("call list")

            # Start reading and keepalive
            self._read_task = asyncio.create_task(self._read_loop())
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())
            return True
        except (ConnectionRefusedError, asyncio.TimeoutError, OSError) as e:
            logger.warning("Cannot connect to pjsua CLI: %s", e)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        if self._read_task:
            self._read_task.cancel()
        if hasattr(self, '_keepalive_task') and self._keepalive_task:
            self._keepalive_task.cancel()
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        self._connected = False
        # Clear state so reconnection emits fresh events
        self.active_accounts.clear()
        self.sip_ready = False
        self.server_reachable = False

    async def send(self, command: str) -> None:
        """Send command to pjsua CLI."""
        if not self._connected or not self._writer:
            logger.warning("Not connected, cannot send: %s", command)
            return
        try:
            self._writer.write(f"{command}\r\n".encode())
            await asyncio.wait_for(self._writer.drain(), timeout=5)
            logger.debug("Sent: %s", command)
        except asyncio.TimeoutError:
            logger.error("Send timed out (pjsua not reading): %s", command)
            self._connected = False
        except Exception as e:
            logger.error("Send failed: %s", e)
            self._connected = False

    # --- Call control commands ---

    async def make_call(self, uri: str, account_id: int = 0) -> None:
        await self.send(f"call new sip:{uri}")

    async def answer(self) -> None:
        await self.send("call answer 200")

    async def hangup(self) -> None:
        await self.send("call hangup")
        # Start a timeout — if call doesn't end within 5s (e.g. broken transport),
        # force-reset call state so the UI isn't stuck
        asyncio.create_task(self._hangup_timeout())

    async def reject(self) -> None:
        await self.send("call answer 486")

    async def set_volume(self, capture: float, playback: float) -> None:
        """Set pjsua software mixer levels (capture and playback)."""
        await self.send(f"V {capture:.2f} {playback:.2f}")

    async def play_tone(self, tone_id: int) -> None:
        """Play tone — disabled until WAV files are available."""
        pass

    async def _keepalive_loop(self) -> None:
        """Periodically poll acc show to get registration state and keep connection alive."""
        try:
            while self._connected:
                await asyncio.sleep(30)
                if self._connected:
                    await self.send("acc show")
        except asyncio.CancelledError:
            pass

    async def _hangup_timeout(self) -> None:
        """Force-reset call state if hangup doesn't complete within 5 seconds.

        When the SIP transport is broken, pjsua can't send BYE and the call
        stays in CONNECTED state. This forces a local reset and pjsua restart.
        """
        try:
            await asyncio.sleep(5)
            if self.call_state not in (CallState.IDLE, CallState.DISCONNECTED):
                logger.warning("Hangup timeout — forcing call state reset and pjsua restart")
                self._stop_quality_poll()
                old_contact = self.current_contact
                self.call_state = CallState.IDLE
                self.current_contact = None
                self.current_codec = None
                self.srtp_active = False
                self.srtp_suite = None
                self._emit_sync("ended", {"destination": old_contact or ""})
                # Restart pjsua to clear the stuck call
                from src.sip.pjsua_manager import pjsua
                await pjsua.restart()
        except asyncio.CancelledError:
            pass

    # --- Output parsing ---

    async def _read_loop(self) -> None:
        """Read and parse pjsua telnet output."""
        try:
            while self._connected:
                data = await self._reader.read(16384)
                if not data:
                    logger.warning("pjsua CLI connection closed")
                    self._connected = False
                    self.active_accounts.clear()
                    self.sip_ready = False
                    self.server_reachable = False
                    await self._emit("backend_disconnected", {})
                    break
                # Strip telnet negotiation bytes (IAC sequences)
                cleaned = bytearray()
                i = 0
                raw = data
                while i < len(raw):
                    if raw[i] == 0xff and i + 2 <= len(raw) - 1:
                        i += 3  # skip IAC + command + option
                    else:
                        cleaned.append(raw[i])
                        i += 1
                self._buffer += bytes(cleaned).decode("utf-8", errors="replace")
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
        # Strip null bytes and bell chars from pjsua output
        data = data.replace("\x00", "").replace("\x07", "").strip()
        if not data or (data.endswith(">") and " " not in data):
            # End of dump_q block — parse collected lines
            if self._collecting_dump_q and self._dump_q_lines:
                self._collecting_dump_q = False
                self._parse_dump_q(self._dump_q_lines)
                self._dump_q_lines = []
            return

        # Collect dump_q multi-line output (pjsua 2.14 format)
        if self._collecting_dump_q:
            self._dump_q_lines.append(data)
            # dump_q ends with RTT line
            if re.search(r"RTT\s+msec", data):
                self._collecting_dump_q = False
                self._parse_dump_q(self._dump_q_lines)
                self._dump_q_lines = []
            elif len(self._dump_q_lines) > 100:
                # Guard against unbounded growth if pjsua crashes mid-output
                logger.warning("dump_q collection exceeded 100 lines, resetting")
                self._collecting_dump_q = False
                self._dump_q_lines = []
            return

        # Start collecting dump_q output — RX pt= is the first stats line
        if re.search(r"RX pt=\d+,\s*last update", data):
            self._collecting_dump_q = True
            self._dump_q_lines = [data]
            return

        # Call state: CONFIRMED
        if re.search(r"Call [0-9] state changed to CONFIRMED", data):
            asyncio.create_task(self.send("call list"))
            asyncio.create_task(self.send("call dump_q"))

        elif m := re.search(r"Current call id\=[0-9] to (.+) \[CONFIRMED\]", data):
            self.call_state = CallState.CONNECTED
            self._start_quality_poll()
            self._emit_sync("connected", {"destination": self.current_contact, "codec": self.current_codec, "connected_at": time.time()})

        # Codec from call dump_q: "#0 audio G722 @16kHz" or "#0 audio PCMU @8kHz"
        elif m := re.search(r"#[0-9] audio (\w+)\s*@", data):
            self.current_codec = m.group(1).upper()
            if self.call_state == CallState.CONNECTED:
                self._emit_sync("codec", {"codec": self.current_codec})

        # SRTP status from call dump_q: "SRTP status: Active Crypto-suite: AES_256_CM_HMAC_SHA1_80"
        elif m := re.search(r"SRTP status:\s*(\w+)", data):
            self.srtp_active = (m.group(1).lower() == "active")
            suite_match = re.search(r"Crypto-suite:\s*(\S+)", data)
            self.srtp_suite = suite_match.group(1) if suite_match else None
            self._emit_sync("srtp", {"active": self.srtp_active, "suite": self.srtp_suite})

        # Call state: DISCONNECTED (pjsua 2.9 uses DISCONNCTD, 2.14 uses DISCONNECTED)
        elif m := re.search(r"\[DISCONN[A-Z]*\] t\: ([^;]+)", data):
            self._stop_quality_poll()
            self.call_state = CallState.IDLE
            self._emit_sync("ended", {"destination": m.group(1)})
            self.current_contact = None
            self.current_codec = None
            self.srtp_active = False
            self.srtp_suite = None

        # pjsua 2.14 format: Call 0 is DISCONNECTED [reason=...]
        elif m := re.search(r"Call [0-9] is DISCONNECTED", data):
            self._stop_quality_poll()
            self.call_state = CallState.IDLE
            self._emit_sync("ended", {"destination": self.current_contact or ""})
            self.current_contact = None
            self.current_codec = None
            self.srtp_active = False
            self.srtp_suite = None

        # Incoming call (pjsua 2.14 outputs on separate lines:
        #   "Incoming call for account 3!"
        #   "From: "user1" <sip:user1@sip.rtegroup.ie>"
        #   "Press ca a to answer or g to reject call")
        elif re.search(r"Incoming call for account", data):
            self.call_state = CallState.INCOMING
            self._incoming_pending = True
        elif (m := re.search(r'^From:\s*(.+)', data)) and getattr(self, '_incoming_pending', False):
            self._incoming_pending = False
            contact = self._resolve_contact(m.group(1))
            self.current_contact = contact
            self._emit_sync("incoming", {"destination": contact})
            # Auto answer
            audio = get_section("audio")
            if audio.get("auto_answer", False):
                logger.info("Auto-answer enabled, answering incoming call from %s", contact)
                asyncio.create_task(self.answer())
        elif re.search(r"Call [0-9] state changed to INCOMING", data):
            self.call_state = CallState.INCOMING
            self._emit_sync("incoming", {"destination": self.current_contact or "Unknown"})
            audio = get_section("audio")
            if audio.get("auto_answer", False):
                logger.info("Auto-answer enabled, answering incoming call from %s", self.current_contact)
                asyncio.create_task(self.answer())

        # Call state: CALLING
        elif re.search(r"Call [0-9] state changed to CALLING", data) or              re.search(r"Current call id\=[0-9] to .+ \[CALLING\]", data):
            self.call_state = CallState.CALLING
            self._emit_sync("calling", {"destination": self.current_contact})

        # Call state: RINGING (180)
        elif re.search(r"Call [0-9] state changed to EARLY \(180 Ringing\)", data) or              re.search(r"Current call id\=[0-9] to .+ \[EARLY\]", data):
            self.call_state = CallState.RINGING
            self._emit_sync("ringing", {"destination": self.current_contact or ""})

        # Registration status (event format and acc show format)
        elif (m := re.search(r"\[.?[0-9]\] sip\:([^\:]+)\: ([0-9]{3})\/[A-z\s]+ \(expires\=(-?[0-9]+)\)", data)) or              (m := re.search(r"sip\:([^\:]+)\: registration.+status\=([0-9]{1,3}) \([A-z]+\)", data)) or              (m := re.search(r"sip\:([^@]+)@[^:]+\: ([0-9]{3})\/", data)):
            account_id = m.group(1)
            status = int(m.group(2))
            was_registered = self.active_accounts.get(account_id)
            is_registered = (status == 200)
            self.active_accounts[account_id] = is_registered

            if is_registered:
                self.server_reachable = True
                if not self.sip_ready:
                    self.sip_ready = True
                    asyncio.create_task(self.play_tone(1))
                # Only emit if state changed (suppress duplicate re-registration events)
                if was_registered != is_registered or was_registered is None:
                    self._emit_sync("account", {"id": account_id, "status": status, "registered": True,
                                                 "sip_ready": self.sip_ready, "server_reachable": self.server_reachable})
            elif status > 200:
                self.server_reachable = False
                if not self.sip_ready:
                    asyncio.create_task(self.play_tone(2))
                # Always emit failures so UI shows disconnection
                self._emit_sync("account", {"id": account_id, "status": status, "registered": False,
                                             "sip_ready": self.sip_ready, "server_reachable": self.server_reachable})

        # Audio device error
        elif "PJMEDIA_EAUD_SYSERR" in data:
            self._emit_sync("audio_error", {"error": "device_error"})

        # STUN/network errors (don't affect server_reachable — these are ICE/NAT issues, not SIP server)
        elif any(err in data for err in ["PJNATH_ESTUNTIMEDOUT", "Error sending STUN request", "PJ_ERESOLVE"]):
            if "not nominated" not in data and "REGISTER" not in data and "registration" not in data:
                self._emit_sync("network_error", {"error": data})

        # Connection errors
        elif ("Connection timed out" in data or "Connection refused" in data) and not self.current_contact:
            self.server_reachable = False
            self._emit_sync("connection_error", {"error": data})

        # Transport errors — server connection lost
        elif "transport error" in data.lower() or "PJSIP_ETPNOTAVAIL" in data:
            self.server_reachable = False
            self._emit_sync("connection_error", {"error": data})

        # SIP error reason
        elif m := re.search(r"\[reason\=([0-9]{3}) \((.+)\)\]", data):
            self._emit_sync("reason", {"code": int(m.group(1)), "verbose": m.group(2)})

        # Debug/other output
        else:
            if data:
                self._emit_sync("debug", {"data": data})

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

    # --- Call quality polling ---

    def _start_quality_poll(self) -> None:
        """Start periodic dump_q polling during a call."""
        self._stop_quality_poll()
        self._quality_poll_task = asyncio.create_task(self._quality_poll_loop())

    def _stop_quality_poll(self) -> None:
        """Stop quality polling."""
        if self._quality_poll_task:
            self._quality_poll_task.cancel()
            self._quality_poll_task = None
        self.call_quality = {}
        self._dump_q_lines = []
        self._collecting_dump_q = False
        self._prev_quality = None
        self._prev_quality_time = 0

    async def _quality_poll_loop(self) -> None:
        """Poll dump_q every 5 seconds while in a call."""
        try:
            await asyncio.sleep(2)  # initial delay — let call settle
            while self.call_state == CallState.CONNECTED:
                await self.send("call dump_q")
                await asyncio.sleep(3)
        except asyncio.CancelledError:
            pass

    def _parse_dump_q(self, lines: list[str]) -> None:
        """Parse pjsua 2.14 dump_q output into quality metrics.

        Format: RX block first, then TX block, then RTT.
        Each block has: total Npkt, pkt loss=N (N.N%), jitter columns, etc.
        Jitter/RTT lines use space-separated columns: min avg max last dev
        """
        quality: dict = {}

        # Track which block we're in (RX comes first, then TX)
        in_rx = False
        in_tx = False

        for line in lines:
            # Block markers
            if re.search(r"RX pt=", line):
                in_rx, in_tx = True, False
            elif re.search(r"TX pt=", line):
                in_rx, in_tx = False, True
            elif re.search(r"RTT\s+msec", line):
                in_rx, in_tx = False, False

            prefix = "rx" if in_rx else "tx" if in_tx else None

            # Packet count: "total 835pkt" or "total 1.0Kpkt"
            if prefix and (m := re.search(r"total\s+([\d.]+)(K?)pkt", line)):
                count = float(m.group(1))
                if m.group(2) == "K":
                    count *= 1000
                quality[f"{prefix}_packets"] = int(count)

            # Packet loss: "pkt loss=0 (0.0%)"
            if prefix and (m := re.search(r"pkt loss\s*=\s*(\d+)\s+\(([\d.]+)%\)", line)):
                quality[f"{prefix}_lost"] = int(m.group(1))
                quality[f"{prefix}_loss_pct"] = float(m.group(2))

            # Byte count: "total 835pkt 27.3KB" or "total 1.0Kpkt 97.7KB"
            if prefix and (m := re.search(r"total\s+[\d.]+K?pkt\s+([\d.]+)(K?)B", line)):
                bytes_val = float(m.group(1))
                if m.group(2) == "K":
                    bytes_val *= 1024
                quality[f"{prefix}_bytes"] = bytes_val

            # Avg bitrate (call-lifetime average): "@avg=12.6Kbps/28.0Kbps"
            if prefix and (m := re.search(r"@avg=([\d.]+)Kbps/([\d.]+)Kbps", line)):
                quality[f"{prefix}_bitrate_avg"] = float(m.group(1))
                quality[f"{prefix}_bitrate_ip_avg"] = float(m.group(2))

            # Jitter: "jitter     :   0.229   6.822  20.208   3.250   4.523"
            # Columns:              min     avg     max     last    dev
            if prefix and (m := re.search(r"jitter\s+:\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", line)):
                quality[f"{prefix}_jitter_avg"] = float(m.group(2))
                quality[f"{prefix}_jitter_max"] = float(m.group(3))
                quality[f"{prefix}_jitter_last"] = float(m.group(4))

            # RTT: "RTT msec      :  21.438  33.245  59.448  25.894  15.245"
            if re.search(r"RTT\s+msec", line):
                if m := re.search(r"RTT\s+msec\s+:\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", line):
                    quality["rtt_avg"] = float(m.group(2))
                    quality["rtt_last"] = float(m.group(4))

        # Calculate instantaneous bitrate from byte count deltas
        now = time.time()
        if self._prev_quality and self._prev_quality_time:
            dt = now - self._prev_quality_time
            if dt > 0.5:  # guard against tiny intervals
                for prefix in ("rx", "tx"):
                    curr_bytes = quality.get(f"{prefix}_bytes")
                    prev_bytes = self._prev_quality.get(f"{prefix}_bytes")
                    if curr_bytes is not None and prev_bytes is not None:
                        delta_bytes = curr_bytes - prev_bytes
                        quality[f"{prefix}_bitrate"] = round(delta_bytes * 8 / dt / 1000, 1)  # Kbps
        self._prev_quality = dict(quality)
        self._prev_quality_time = now

        # Remove internal byte counts from broadcast
        quality.pop("rx_bytes", None)
        quality.pop("tx_bytes", None)

        # Include configured target bitrate
        audio = get_section("audio")
        quality["target_bitrate"] = audio.get("bitrate", 64000) / 1000  # Kbps

        if quality:
            self.call_quality = quality
            self._emit_sync("quality", quality)

    def _emit_sync(self, event: str, data: dict) -> None:
        if self._on_event:
            asyncio.create_task(self._on_event(event, data))

    async def _emit(self, event: str, data: dict) -> None:
        if self._on_event:
            await self._on_event(event, data)
