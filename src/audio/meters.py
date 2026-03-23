"""Live audio level metering — reads levels from pjsua conference bridge.

Uses pjsua's telnet CLI 'conf_stat' command to read tx/rx signal levels.
No separate audio device access needed — piggybacks on pjsua's own audio.
Zero additional CPU or device conflicts.
"""

import asyncio
import logging
import re
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Metering rate — ~15fps (67ms interval)
METER_INTERVAL = 0.067

# Regex to parse conf_stat output
# Port #00[48KHz/2/20ms/1920]  tx_level:   3.2, rx_level:   0.0
LEVEL_RE = re.compile(
    r"Port\s+#(\d+).*tx_level:\s*([\d.]+),\s*rx_level:\s*([\d.]+)"
)


class AudioMeter:
    """Reads live audio levels from pjsua conference bridge stats.

    tx_level = what pjsua is sending (capture/mic level)
    rx_level = what pjsua is receiving (playback/remote audio level)

    Levels are in pjsua's arbitrary scale (0.0 = silence, ~4-5 = loud).
    We normalize to 0-100 for display.
    """

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._on_levels: Optional[Callable] = None
        self._telnet: Optional[object] = None

        # Current levels (0-100)
        self.capture_left = 0
        self.capture_right = 0
        self.playback_left = 0
        self.playback_right = 0

    def on_levels(self, callback: Callable) -> None:
        """Register callback: callback(capture_l, capture_r, playback_l, playback_r)"""
        self._on_levels = callback

    def set_telnet(self, telnet) -> None:
        """Set the pjsua telnet client to query levels from."""
        self._telnet = telnet

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Audio metering started (pjsua conf_stat)")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Audio metering stopped")

    async def _poll_loop(self) -> None:
        """Poll pjsua conf_stat for signal levels."""
        while self._running:
            try:
                if self._telnet and self._telnet.connected:
                    await self._read_levels()
                await asyncio.sleep(METER_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug("Metering poll error: %s", e)
                await asyncio.sleep(1)

    async def _read_levels(self) -> None:
        """Send conf_stat and parse the response for signal levels.

        Since the telnet client processes all output through _parse_line,
        we need a different approach: send the command and capture the
        debug events that come back.
        """
        if not self._telnet:
            return

        # Send the command — the response will come through the telnet read loop
        # We'll parse it from the debug output
        await self._telnet.send("conf_stat")

        # Give pjsua time to respond
        await asyncio.sleep(0.05)

    def parse_conf_stat_line(self, line: str) -> bool:
        """Parse a conf_stat output line. Called from telnet debug handler.

        Returns True if the line was a conf_stat level line.
        """
        m = LEVEL_RE.search(line)
        if not m:
            return False

        port = int(m.group(1))
        tx = float(m.group(2))
        rx = float(m.group(3))

        # Normalize pjsua levels (0-5 typical range) to 0-100
        # pjsua uses RMS-like levels, ~4.0 is loud speech
        tx_pct = min(100, int((tx / 5.0) * 100))
        rx_pct = min(100, int((rx / 5.0) * 100))

        # Port 0 is the main conference port (sound device)
        if port == 0:
            # tx = what we're sending = capture/mic
            # rx = what we're receiving = playback/remote
            self.capture_left = tx_pct
            self.capture_right = tx_pct  # pjsua reports mono levels
            self.playback_left = rx_pct
            self.playback_right = rx_pct

            # Emit levels
            if self._on_levels:
                asyncio.create_task(self._on_levels(
                    self.capture_left, self.capture_right,
                    self.playback_left, self.playback_right,
                ))
            return True

        return False


# Singleton
audio_meter = AudioMeter()
