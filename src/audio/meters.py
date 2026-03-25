"""Audio metering — stub (disabled)."""

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class AudioMeter:
    """Stub — metering disabled."""

    def __init__(self):
        self.capture_left = 0
        self.capture_right = 0
        self.playback_left = 0
        self.playback_right = 0

    def on_levels(self, callback: Callable) -> None:
        pass

    def set_telnet(self, telnet) -> None:
        pass

    async def start(self) -> None:
        logger.info("Audio metering disabled")

    async def stop(self) -> None:
        pass

    def parse_conf_stat_line(self, line: str) -> bool:
        return False


audio_meter = AudioMeter()
