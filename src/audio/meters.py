"""Live audio level metering — reads PCM from ALSA dsnoop tap.

Lightweight: reads small chunks from the shared capture device,
computes RMS, and emits normalized 0-100 levels via callback.
No extra processes — runs as an asyncio task in the main app.
"""

import asyncio
import logging
import struct
import math
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Metering rate — ~15fps
METER_INTERVAL = 0.067

# ALSA device for capture metering
METER_DEVICE = "meter_capture"
SAMPLE_RATE = 48000
CHANNELS = 1
PERIOD_SIZE = 480  # 10ms at 48kHz


class AudioMeter:
    """Reads live audio levels from ALSA capture via dsnoop.

    Levels are RMS-normalized to 0-100 for display.
    """

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._on_levels: Optional[Callable] = None
        self._telnet: Optional[object] = None
        self._pcm = None

        # Current levels (0-100)
        self.capture_left = 0
        self.capture_right = 0
        self.playback_left = 0
        self.playback_right = 0

    def on_levels(self, callback: Callable) -> None:
        """Register callback: callback(capture_l, capture_r, playback_l, playback_r)"""
        self._on_levels = callback

    def set_telnet(self, telnet) -> None:
        """Set the pjsua telnet client (unused — kept for API compat)."""
        self._telnet = telnet

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._meter_loop())
        logger.info("Audio metering started (ALSA dsnoop)")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._close_pcm()
        logger.info("Audio metering stopped")

    def _open_pcm(self) -> bool:
        """Open ALSA capture device for metering."""
        try:
            import alsaaudio
            self._pcm = alsaaudio.PCM(
                type=alsaaudio.PCM_CAPTURE,
                mode=alsaaudio.PCM_NORMAL,
                device=METER_DEVICE,
                rate=SAMPLE_RATE,
                channels=CHANNELS,
                format=alsaaudio.PCM_FORMAT_S16_LE,
                periodsize=PERIOD_SIZE,
            )
            # Test read — if it fails, the device isn't ready
            length, _ = self._pcm.read()
            if length < 0:
                self._pcm.close()
                self._pcm = None
                return False
            logger.info("Opened ALSA capture device for metering")
            return True
        except Exception as e:
            logger.debug("Cannot open ALSA capture for metering: %s", e)
            self._pcm = None
            return False

    def _close_pcm(self):
        if self._pcm:
            try:
                self._pcm.close()
            except Exception:
                pass
            self._pcm = None

    async def _meter_loop(self) -> None:
        """Metering disabled — ALSA dsnoop conflicts with pjsua on Pi."""
        pass

    def _blocking_meter_loop(self) -> None:
        """Read PCM data and compute RMS levels (runs in dedicated thread)."""
        import time

        retry_delay = 2
        while self._running:
            try:
                if not self._pcm:
                    if not self._open_pcm():
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 30)
                        continue
                    retry_delay = 2

                length, data = self._pcm.read()

                if length == -32:
                    # EPIPE — xrun, just retry
                    time.sleep(0.1)
                    continue

                if length > 0 and data:
                    if not hasattr(self, '_logged_first'):
                        self._logged_first = True
                        logger.info("Metering active — first successful read (%d frames)", length)
                    rms = self._compute_rms(data, length)
                    level = min(100, int((rms / 2000) * 100))
                    self.capture_left = level
                    self.capture_right = level

                    # Levels are set on self — broadcast task picks them up
                elif length < 0:
                    logger.warning("ALSA meter read error: %d", length)
                    self._close_pcm()
                    time.sleep(2)
                    continue

                time.sleep(METER_INTERVAL)

            except Exception as e:
                logger.debug("Metering error: %s", e)
                self._close_pcm()
                time.sleep(5)

    @staticmethod
    def _compute_rms(data: bytes, frames: int) -> float:
        """Compute RMS of S16_LE PCM data."""
        if len(data) < frames * 2:
            return 0.0
        samples = struct.unpack(f"<{frames}h", data[:frames * 2])
        if not samples:
            return 0.0
        sum_sq = sum(s * s for s in samples)
        return math.sqrt(sum_sq / len(samples))

    def parse_conf_stat_line(self, line: str) -> bool:
        """Legacy — no longer used. Returns False."""
        return False


# Singleton
audio_meter = AudioMeter()
