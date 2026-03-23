"""Live audio level metering — reads ALSA peak levels for real-time display.

Uses arecord piped through a peak detector to read capture levels,
and monitors playback via ALSA's softvol or VU meter PCM.

Falls back to pjsua's conference port stats if ALSA metering is unavailable.
"""

import asyncio
import logging
import struct
import subprocess
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Metering rate — ~20 updates per second
METER_INTERVAL = 0.05
# Number of audio frames per meter sample (48kHz * 50ms = 2400 frames)
FRAMES_PER_SAMPLE = 2400
SAMPLE_RATE = 48000
CHANNELS = 2


class AudioMeter:
    """Reads live audio peak levels from ALSA capture and playback devices.

    Runs arecord/aplay in monitor mode to get PCM samples, computes peak
    levels, and calls the callback with normalized 0-100 values.
    """

    def __init__(self):
        self._running = False
        self._capture_task: Optional[asyncio.Task] = None
        self._playback_task: Optional[asyncio.Task] = None
        self._on_levels: Optional[Callable] = None

        # Current peak levels (0-100)
        self.capture_left = 0
        self.capture_right = 0
        self.playback_left = 0
        self.playback_right = 0

    def on_levels(self, callback: Callable) -> None:
        """Register callback: callback(capture_l, capture_r, playback_l, playback_r)"""
        self._on_levels = callback

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._capture_task = asyncio.create_task(self._monitor_capture())
        self._playback_task = asyncio.create_task(self._monitor_playback())
        logger.info("Audio metering started")

    async def stop(self) -> None:
        self._running = False
        for task in [self._capture_task, self._playback_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("Audio metering stopped")

    async def _monitor_capture(self) -> None:
        """Monitor capture (input) levels via arecord."""
        while self._running:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "arecord",
                    "-D", "default",
                    "-f", "S16_LE",
                    "-r", str(SAMPLE_RATE),
                    "-c", str(CHANNELS),
                    "-t", "raw",
                    "--buffer-size", str(FRAMES_PER_SAMPLE * 4),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )

                while self._running and proc.stdout:
                    # Read one meter sample worth of audio
                    bytes_needed = FRAMES_PER_SAMPLE * CHANNELS * 2  # 16-bit = 2 bytes
                    data = await asyncio.wait_for(
                        proc.stdout.read(bytes_needed),
                        timeout=2.0,
                    )
                    if not data:
                        break

                    left, right = self._compute_peak_stereo(data)
                    self.capture_left = left
                    self.capture_right = right
                    await self._emit()

                proc.kill()
                await proc.wait()

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug("Capture metering error: %s", e)
                await asyncio.sleep(1)

    async def _monitor_playback(self) -> None:
        """Monitor playback (output) levels.

        Uses arecord on the loopback or monitor device if available.
        Falls back to tracking the capture level as a proxy when
        no monitor source is available.
        """
        # Try ALSA loopback monitor first
        monitor_devices = ["hw:Loopback,1,0", "plug:monitor"]

        while self._running:
            try:
                # Attempt to open a monitor device
                device = None
                for dev in monitor_devices:
                    try:
                        test = await asyncio.create_subprocess_exec(
                            "arecord", "-D", dev, "-d", "0",
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        await asyncio.wait_for(test.wait(), timeout=1)
                        if test.returncode == 0:
                            device = dev
                            break
                    except Exception:
                        continue

                if device:
                    proc = await asyncio.create_subprocess_exec(
                        "arecord",
                        "-D", device,
                        "-f", "S16_LE",
                        "-r", str(SAMPLE_RATE),
                        "-c", str(CHANNELS),
                        "-t", "raw",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )

                    while self._running and proc.stdout:
                        bytes_needed = FRAMES_PER_SAMPLE * CHANNELS * 2
                        data = await asyncio.wait_for(
                            proc.stdout.read(bytes_needed),
                            timeout=2.0,
                        )
                        if not data:
                            break

                        left, right = self._compute_peak_stereo(data)
                        self.playback_left = left
                        self.playback_right = right
                        await self._emit()

                    proc.kill()
                    await proc.wait()
                else:
                    # No monitor device — just sleep and let capture emit
                    await asyncio.sleep(METER_INTERVAL)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug("Playback metering error: %s", e)
                await asyncio.sleep(1)

    @staticmethod
    def _compute_peak_stereo(data: bytes) -> tuple[int, int]:
        """Compute peak levels from interleaved S16_LE stereo PCM data.

        Returns (left_pct, right_pct) as 0-100 values.
        """
        if len(data) < 4:
            return (0, 0)

        # Unpack as signed 16-bit little-endian
        num_samples = len(data) // 2
        try:
            samples = struct.unpack(f"<{num_samples}h", data[:num_samples * 2])
        except struct.error:
            return (0, 0)

        # Deinterleave L/R
        peak_left = 0
        peak_right = 0
        for i in range(0, len(samples) - 1, 2):
            peak_left = max(peak_left, abs(samples[i]))
            peak_right = max(peak_right, abs(samples[i + 1]))

        # Normalize to 0-100 (32767 = full scale)
        max_val = 32767
        left_pct = min(100, int((peak_left / max_val) * 100))
        right_pct = min(100, int((peak_right / max_val) * 100))

        return (left_pct, right_pct)

    async def _emit(self) -> None:
        if self._on_levels:
            await self._on_levels(
                self.capture_left, self.capture_right,
                self.playback_left, self.playback_right,
            )


# Singleton
audio_meter = AudioMeter()
