"""Display manager — starts the appropriate display driver based on config.

Modes:
  none   — No display, do nothing.
  7inch  — Launch Cage (Wayland compositor) with a lightweight browser
           pointing at the local web UI.
  3inch  — Launch the pygame framebuffer UI directly on /dev/fb1.
"""

import asyncio
import logging
import shutil
import subprocess
from typing import Optional

from src.config.settings import get_section

logger = logging.getLogger(__name__)


class DisplayManager:
    """Manages the display subsystem alongside the FastAPI server."""

    def __init__(self):
        self._mode: str = "none"
        self._task: Optional[asyncio.Task] = None
        self._process: Optional[asyncio.subprocess.Process] = None
        self._fb_ui = None  # FramebufferUI instance for 3inch mode

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Read display config and start the appropriate driver."""
        config = get_section("display")
        self._mode = config.get("mode", "none")

        if self._mode == "none":
            logger.info("Display mode: none — display subsystem disabled")
            return

        if self._mode == "7inch":
            self._task = asyncio.create_task(self._run_7inch(config))
            logger.info("Display mode: 7inch — starting Cage + browser")

        elif self._mode == "3inch":
            self._task = asyncio.create_task(self._run_3inch(config))
            logger.info("Display mode: 3inch — starting pygame framebuffer UI")

        else:
            logger.warning("Unknown display mode: %s — ignoring", self._mode)

    async def stop(self) -> None:
        """Stop the display subsystem."""
        if self._fb_ui is not None:
            self._fb_ui.stop()
            self._fb_ui = None

        if self._process is not None:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except (ProcessLookupError, asyncio.TimeoutError):
                try:
                    self._process.kill()
                except ProcessLookupError:
                    pass
            self._process = None

        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("Display manager stopped")

    # ── 7-inch: Cage + browser ───────────────────────────────────────

    async def _run_7inch(self, config: dict) -> None:
        """Launch Cage Wayland compositor with a kiosk browser."""
        # Determine browser — prefer chromium, fall back to firefox
        browser = None
        for candidate in ("chromium-browser", "chromium", "firefox-esr", "firefox"):
            if shutil.which(candidate):
                browser = candidate
                break

        if not browser:
            logger.error("No suitable browser found for 7inch display mode")
            return

        if not shutil.which("cage"):
            logger.error("cage not installed — cannot start 7inch display. "
                         "Install with: sudo apt install cage")
            return

        # Build browser command — kiosk mode, pointing at local web UI
        import os
        port = os.environ.get("RTESIP_PORT", "80")
        url = f"http://127.0.0.1:{port}?kiosk=1"
        if "chromium" in browser:
            browser_cmd = (
                f"{browser} --kiosk --noerrdialogs --disable-infobars "
                f"--disable-session-crashed-bubble --no-first-run "
                f"--disable-translate --disable-features=TranslateUI "
                f"--check-for-update-interval=31536000 {url}"
            )
        else:
            browser_cmd = f"{browser} --kiosk {url}"

        # Rotation
        rotation = config.get("rotation", 0)
        env = {
            "WLR_LIBINPUT_NO_DEVICES": "1",
            "XDG_RUNTIME_DIR": "/run/user/0",
        }
        if rotation:
            env["WLR_OUTPUT_TRANSFORM"] = "90"

        cage_cmd = f"cage -- {browser_cmd}"
        logger.info("Starting: %s", cage_cmd)

        try:
            self._process = await asyncio.create_subprocess_shell(
                cage_cmd,
                env={**dict(__import__("os").environ), **env},
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await self._process.communicate()
            if self._process.returncode and self._process.returncode != 0:
                logger.error("Cage exited with code %d: %s",
                             self._process.returncode,
                             stderr.decode(errors="replace")[:500])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Failed to start 7inch display: %s", e)

    # ── 3-inch: pygame framebuffer ───────────────────────────────────

    async def _run_3inch(self, config: dict) -> None:
        """Launch the pygame framebuffer UI for the 3" SPI display."""
        from src.display.framebuffer import FramebufferUI

        # Get password hash for WebSocket auth
        security = get_section("security")
        pw_hash = security.get("gui_password_hash", "")

        # Determine framebuffer device
        display_type = config.get("type", "35generic")
        if display_type == "35adafruit":
            fb_device = "/dev/fb1"
        else:
            # Generic SPI displays typically use fb1, but check fb0 as fallback
            fb_device = "/dev/fb1"

        # Set backlight brightness if supported
        brightness = config.get("brightness", 255)
        self._set_backlight(brightness)

        self._fb_ui = FramebufferUI(
            ws_url="ws://127.0.0.1:8000/ws",
            password_hash=pw_hash,
            fb_device=fb_device,
        )

        try:
            await self._fb_ui.start()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Framebuffer UI crashed: %s", e)

    @staticmethod
    def _set_backlight(brightness: int) -> None:
        """Set display backlight brightness (0-255) via sysfs."""
        bl_paths = [
            "/sys/class/backlight/spi/brightness",
            "/sys/class/backlight/fb_ili9486/brightness",
            "/sys/class/backlight/fb_st7796s/brightness",
        ]
        for path in bl_paths:
            try:
                with open(path, "w") as f:
                    f.write(str(max(0, min(255, brightness))))
                logger.info("Set backlight brightness to %d via %s", brightness, path)
                return
            except (FileNotFoundError, PermissionError):
                continue


# Module-level singleton for use in FastAPI lifespan
display_manager = DisplayManager()
