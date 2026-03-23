"""Pygame framebuffer UI for 3" SPI touchscreen (480x320).

Renders directly to /dev/fb1 (SPI display framebuffer) without X11.
Connects to the FastAPI WebSocket on localhost for real-time call state
and volume levels.

Touch input via /dev/input/touchscreen (evdev) or pygame mouse fallback.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Screen dimensions for 3" SPI display
WIDTH = 480
HEIGHT = 320
FPS = 15

# Colours
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREY = (60, 60, 60)
DARK_GREY = (40, 40, 40)
LIGHT_GREY = (160, 160, 160)
GREEN = (0, 200, 80)
RED = (220, 50, 50)
AMBER = (255, 180, 0)
BLUE = (40, 120, 220)
DARK_GREEN = (0, 100, 40)
DARK_RED = (100, 20, 20)
CYAN = (0, 180, 200)

# Layout constants
TOP_BAR_H = 36
BOTTOM_BAR_H = 64
METER_WIDTH = 16
METER_GAP = 6
METER_MARGIN = 12


@dataclass
class DisplayState:
    """Tracks current UI state from WebSocket events."""
    call_state: str = "idle"
    current_contact: str = ""
    sip_ready: bool = False
    connected: bool = False
    # Volume levels (0-100+)
    capture_left: int = 100
    capture_right: int = 100
    playback_left: int = 100
    playback_right: int = 100
    # Accounts
    accounts: dict = field(default_factory=dict)


class FramebufferUI:
    """Pygame-based framebuffer UI for 3" SPI touchscreen."""

    def __init__(self, ws_url: str = "ws://127.0.0.1:8000/ws",
                 password_hash: str = "", fb_device: str = "/dev/fb1"):
        self.ws_url = ws_url
        self.password_hash = password_hash
        self.fb_device = fb_device
        self.state = DisplayState()
        self._running = False
        self._ws = None
        self._screen = None
        self._font = None
        self._font_sm = None
        self._font_lg = None
        self._clock = None
        self._buttons: list[dict] = []
        self._touch_feedback: Optional[dict] = None
        self._touch_feedback_time: float = 0

    async def start(self) -> None:
        """Start the framebuffer UI — runs pygame loop and WebSocket client."""
        self._running = True

        # Initialise pygame for framebuffer rendering
        self._init_pygame()

        # Run WS client and render loop concurrently
        ws_task = asyncio.create_task(self._ws_loop())
        render_task = asyncio.create_task(self._render_loop())

        try:
            await asyncio.gather(ws_task, render_task)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            self._cleanup_pygame()

    def stop(self) -> None:
        """Signal the UI to stop."""
        self._running = False

    def _init_pygame(self) -> None:
        """Initialise pygame with framebuffer driver."""
        import pygame

        # Use fbcon driver for direct framebuffer access (no X11)
        if os.path.exists(self.fb_device):
            os.environ["SDL_FBDEV"] = self.fb_device
            os.environ["SDL_VIDEODRIVER"] = "fbcon"
        else:
            # Fallback for development — use windowed mode
            os.environ.setdefault("SDL_VIDEODRIVER", "x11")
            logger.warning("Framebuffer %s not found, using windowed mode", self.fb_device)

        # Use evdev touchscreen if available
        if os.path.exists("/dev/input/touchscreen"):
            os.environ["SDL_MOUSEDEV"] = "/dev/input/touchscreen"
            os.environ["SDL_MOUSEDRV"] = "TSLIB"

        pygame.init()
        pygame.mouse.set_visible(False)

        self._screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("SIP Reporter")

        # Fonts — DejaVu is available on Raspberry Pi OS
        try:
            self._font = pygame.font.Font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            self._font_sm = pygame.font.Font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
            self._font_lg = pygame.font.Font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except FileNotFoundError:
            self._font = pygame.font.SysFont("sans", 16)
            self._font_sm = pygame.font.SysFont("sans", 12)
            self._font_lg = pygame.font.SysFont("sansbold", 24)

        self._clock = pygame.time.Clock()

    def _cleanup_pygame(self) -> None:
        """Shut down pygame."""
        try:
            import pygame
            pygame.quit()
        except Exception:
            pass

    # ── WebSocket client ─────────────────────────────────────────────

    async def _ws_loop(self) -> None:
        """Connect to FastAPI WebSocket and receive state updates."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets package not installed — display WS client disabled")
            return

        while self._running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    self._ws = ws
                    self.state.connected = True
                    logger.info("Display WS connected to %s", self.ws_url)

                    # Authenticate
                    await self._authenticate(ws)

                    # Read events
                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            msg = json.loads(raw)
                            self._handle_ws_event(msg)
                        except json.JSONDecodeError:
                            pass

            except Exception as e:
                logger.warning("Display WS error: %s — reconnecting in 3s", e)
                self.state.connected = False
                self._ws = None
                await asyncio.sleep(3)

    async def _authenticate(self, ws) -> None:
        """Perform challenge-response authentication."""
        await ws.send(json.dumps({"command": "authRequest"}))

        raw = await ws.recv()
        msg = json.loads(raw)
        if msg.get("event") != "challenge":
            return

        challenge = msg["challenge"]
        response = hashlib.sha256(f"{self.password_hash}{challenge}".encode()).hexdigest()
        await ws.send(json.dumps({"command": "challengeResponse", "response": response}))

    def _handle_ws_event(self, msg: dict) -> None:
        """Update local state from a WebSocket event."""
        event = msg.get("event", "")

        if event == "state":
            self.state.call_state = msg.get("call_state", "idle")
            self.state.current_contact = msg.get("current_contact", "") or ""
            self.state.sip_ready = msg.get("sip_ready", False)
            self.state.accounts = msg.get("accounts", {})

        elif event == "callState":
            self.state.call_state = msg.get("state", "idle")
            if "remote" in msg:
                self.state.current_contact = msg["remote"]
            if self.state.call_state == "idle":
                self.state.current_contact = ""

        elif event == "levels":
            self.state.capture_left = msg.get("cl", 0)
            self.state.capture_right = msg.get("cr", 0)
            self.state.playback_left = msg.get("pl", 0)
            self.state.playback_right = msg.get("pr", 0)

        elif event == "registration":
            acc = msg.get("account", "")
            registered = msg.get("registered", False)
            if acc:
                self.state.accounts[acc] = registered
            self.state.sip_ready = any(self.state.accounts.values())

    # ── Touch / WS commands ──────────────────────────────────────────

    async def _send_command(self, command: str, **kwargs) -> None:
        """Send a command to the FastAPI WebSocket."""
        if self._ws:
            try:
                await self._ws.send(json.dumps({"command": command, **kwargs}))
            except Exception as e:
                logger.warning("Failed to send command %s: %s", command, e)

    # ── Render loop ──────────────────────────────────────────────────

    async def _render_loop(self) -> None:
        """Main render loop — draw UI and handle touch events at ~15fps."""
        import pygame

        while self._running:
            # Process pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    await self._handle_touch(event.pos)
                elif event.type == pygame.FINGERDOWN:
                    # Normalised touch coordinates
                    x = int(event.x * WIDTH)
                    y = int(event.y * HEIGHT)
                    await self._handle_touch((x, y))

            # Draw
            self._draw()
            pygame.display.flip()

            # Limit frame rate for SPI bandwidth
            self._clock.tick(FPS)
            # Yield to event loop
            await asyncio.sleep(0)

    async def _handle_touch(self, pos: tuple[int, int]) -> None:
        """Check if a touch hit any active button and send the command."""
        import pygame
        x, y = pos

        for btn in self._buttons:
            rect = btn["rect"]
            if rect.collidepoint(x, y):
                self._touch_feedback = btn
                self._touch_feedback_time = time.monotonic()
                cmd = btn.get("command")
                if cmd:
                    await self._send_command(cmd, **btn.get("args", {}))
                break

    # ── Drawing ──────────────────────────────────────────────────────

    def _draw(self) -> None:
        """Render the full UI frame."""
        import pygame

        self._screen.fill(BLACK)
        self._buttons.clear()

        self._draw_top_bar()
        self._draw_centre()
        self._draw_meters()
        self._draw_bottom_bar()

    def _draw_top_bar(self) -> None:
        """Top bar: branding, clock, connection indicator."""
        import pygame

        # Background
        pygame.draw.rect(self._screen, DARK_GREY, (0, 0, WIDTH, TOP_BAR_H))

        # Branding
        title = self._font.render("SIP Reporter", True, WHITE)
        self._screen.blit(title, (10, 8))

        # Clock
        now = datetime.now().strftime("%H:%M:%S")
        clock_surf = self._font_sm.render(now, True, LIGHT_GREY)
        self._screen.blit(clock_surf, (WIDTH // 2 - clock_surf.get_width() // 2, 11))

        # Connection status dot
        dot_colour = GREEN if self.state.connected and self.state.sip_ready else (
            AMBER if self.state.connected else RED
        )
        pygame.draw.circle(self._screen, dot_colour, (WIDTH - 20, TOP_BAR_H // 2), 7)

        # Status label next to dot
        if self.state.sip_ready:
            label = "SIP"
        elif self.state.connected:
            label = "WS"
        else:
            label = "OFF"
        lbl_surf = self._font_sm.render(label, True, LIGHT_GREY)
        self._screen.blit(lbl_surf, (WIDTH - 20 - lbl_surf.get_width() - 12, 11))

    def _draw_centre(self) -> None:
        """Centre area: call state and remote party."""
        import pygame

        centre_y = TOP_BAR_H
        centre_h = HEIGHT - TOP_BAR_H - BOTTOM_BAR_H
        # Usable width excludes meter bars on both sides
        meter_total_w = METER_MARGIN + (METER_WIDTH * 2 + METER_GAP) + METER_MARGIN
        content_x = meter_total_w
        content_w = WIDTH - meter_total_w * 2

        state = self.state.call_state
        state_labels = {
            "idle": ("Idle", LIGHT_GREY),
            "calling": ("Calling...", AMBER),
            "ringing": ("Ringing...", AMBER),
            "incoming": ("Incoming Call", CYAN),
            "connected": ("On Air", GREEN),
            "disconnected": ("Disconnected", RED),
        }
        label, colour = state_labels.get(state, ("Idle", LIGHT_GREY))

        # State label — large
        state_surf = self._font_lg.render(label, True, colour)
        sx = content_x + (content_w - state_surf.get_width()) // 2
        sy = centre_y + centre_h // 2 - 30
        self._screen.blit(state_surf, (sx, sy))

        # Remote party name
        contact = self.state.current_contact
        if contact:
            # Truncate long names
            if len(contact) > 30:
                contact = contact[:27] + "..."
            contact_surf = self._font.render(contact, True, WHITE)
            cx = content_x + (content_w - contact_surf.get_width()) // 2
            cy = sy + 34
            self._screen.blit(contact_surf, (cx, cy))

        # Registration info when idle
        if state == "idle" and not contact:
            reg_count = sum(1 for v in self.state.accounts.values() if v)
            total = len(self.state.accounts)
            if total > 0:
                reg_text = f"{reg_count}/{total} registered"
                reg_colour = GREEN if reg_count == total else AMBER
            else:
                reg_text = "No SIP accounts"
                reg_colour = LIGHT_GREY
            reg_surf = self._font_sm.render(reg_text, True, reg_colour)
            rx = content_x + (content_w - reg_surf.get_width()) // 2
            self._screen.blit(reg_surf, (rx, sy + 34))

    def _draw_meters(self) -> None:
        """Draw vertical level bars for L/R input (left side) and output (right side)."""
        import pygame

        centre_y = TOP_BAR_H + 4
        bar_h = HEIGHT - TOP_BAR_H - BOTTOM_BAR_H - 8

        # Input meters (left side)
        self._draw_meter_pair(
            x=METER_MARGIN,
            y=centre_y,
            h=bar_h,
            level_l=self.state.capture_left,
            level_r=self.state.capture_right,
            label="IN",
        )

        # Output meters (right side)
        pair_w = METER_WIDTH * 2 + METER_GAP
        self._draw_meter_pair(
            x=WIDTH - METER_MARGIN - pair_w,
            y=centre_y,
            h=bar_h,
            level_l=self.state.playback_left,
            level_r=self.state.playback_right,
            label="OUT",
        )

    def _draw_meter_pair(self, x: int, y: int, h: int,
                         level_l: int, level_r: int, label: str) -> None:
        """Draw a pair of vertical meter bars with a label underneath."""
        import pygame

        # Label above
        lbl = self._font_sm.render(label, True, LIGHT_GREY)
        lbl_x = x + (METER_WIDTH * 2 + METER_GAP - lbl.get_width()) // 2
        self._screen.blit(lbl, (lbl_x, y))

        bar_y = y + 16
        bar_h = h - 20

        for i, level in enumerate((level_l, level_r)):
            bx = x + i * (METER_WIDTH + METER_GAP)

            # Background track
            pygame.draw.rect(self._screen, GREY, (bx, bar_y, METER_WIDTH, bar_h))

            # Filled portion (bottom-up)
            pct = min(level, 150) / 150  # normalise to 150% max
            fill_h = int(bar_h * pct)
            if fill_h > 0:
                fill_y = bar_y + bar_h - fill_h
                # Colour gradient: green -> amber -> red
                if pct < 0.65:
                    colour = GREEN
                elif pct < 0.85:
                    colour = AMBER
                else:
                    colour = RED
                pygame.draw.rect(self._screen, colour, (bx, fill_y, METER_WIDTH, fill_h))

    def _draw_bottom_bar(self) -> None:
        """Bottom bar: context-sensitive buttons."""
        import pygame

        bar_y = HEIGHT - BOTTOM_BAR_H
        pygame.draw.rect(self._screen, DARK_GREY, (0, bar_y, WIDTH, BOTTOM_BAR_H))

        state = self.state.call_state

        if state == "incoming":
            # Accept + Reject buttons
            self._draw_button(
                x=20, y=bar_y + 10, w=200, h=44,
                text="Accept", bg=GREEN, fg=BLACK,
                command="answer",
            )
            self._draw_button(
                x=WIDTH - 220, y=bar_y + 10, w=200, h=44,
                text="Reject", bg=RED, fg=WHITE,
                command="reject",
            )

        elif state in ("calling", "ringing", "connected"):
            # Hang up button — centred, full width touch target
            self._draw_button(
                x=WIDTH // 2 - 120, y=bar_y + 10, w=240, h=44,
                text="Hang Up", bg=RED, fg=WHITE,
                command="hangup",
            )

        else:
            # Idle — show hint
            hint = self._font_sm.render("Use web UI to place calls", True, LIGHT_GREY)
            hx = WIDTH // 2 - hint.get_width() // 2
            self._screen.blit(hint, (hx, bar_y + 22))

    def _draw_button(self, x: int, y: int, w: int, h: int,
                     text: str, bg: tuple, fg: tuple,
                     command: str, args: dict = None) -> None:
        """Draw a touchable button and register it for hit testing."""
        import pygame

        rect = pygame.Rect(x, y, w, h)

        # Touch feedback — brief highlight
        is_pressed = (
            self._touch_feedback is not None
            and self._touch_feedback.get("command") == command
            and (time.monotonic() - self._touch_feedback_time) < 0.2
        )

        if is_pressed:
            # Lighten the colour
            draw_bg = tuple(min(c + 60, 255) for c in bg)
        else:
            draw_bg = bg

        pygame.draw.rect(self._screen, draw_bg, rect, border_radius=6)
        pygame.draw.rect(self._screen, WHITE, rect, width=1, border_radius=6)

        # Text centred in button
        txt_surf = self._font.render(text, True, fg)
        tx = x + (w - txt_surf.get_width()) // 2
        ty = y + (h - txt_surf.get_height()) // 2
        self._screen.blit(txt_surf, (tx, ty))

        self._buttons.append({
            "rect": rect,
            "command": command,
            "args": args or {},
        })
