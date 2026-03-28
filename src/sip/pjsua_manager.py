"""Manage pjsua as a subprocess — config generation, start, stop, restart.

- pjsua runs with --use-cli --cli-telnet-port=9090 --no-cli-console
- Control plane connects via telnet to send commands and parse output
- pjsua runs at RT priority 99 via chrt
- Automatic restart on unexpected exit
"""

import asyncio
import logging
import signal
from pathlib import Path
from typing import Optional

from src.config.settings import get_section, DATA_DIR
from src.audio.devices import resolve_device

logger = logging.getLogger(__name__)

PJSUA_BIN = "/usr/local/bin/pjsua"
PJSUA_CONF = DATA_DIR / "pjsua.conf"
PID_FILE = Path("/run/rtesip/pjsua.pid")
CLI_PORT = 9090  # Telnet CLI port (avoid 8000 conflict with our API)

# Audio files
READY_WAV = Path("/opt/rtesip/assets/rdy.wav")
ERROR_WAV = Path("/opt/rtesip/assets/err.wav")


def generate_config() -> str:
    """Generate pjsua config from current settings."""
    sip = get_section("sip")
    audio = get_section("audio")

    lines = [
        # Base config
        f"--log-level={sip.get('log_level', 3)}",
        "--clock-rate=48000",
        "--snd-clock-rate=48000",
        "--quality=10",
        # "--use-compact-form",  # disabled for Twilio compatibility
        "--use-ice",  # Re-enabled for Twilio — causes Bad Request errors with some STUN servers
        "--max-calls=1",
        "--no-vad",
        "--ec-tail=200",
        "--snd-auto-close=0",
        f"--use-cli",
        f"--cli-telnet-port={CLI_PORT}",
        "--no-cli-console",
    ]

    # Codecs — enable wanted, disable unwanted
    for codec in sip.get("codecs", ["opus/48000/2", "L16/48000/1", "G722/16000/1", "PCMA/8000/1", "PCMU/8000/1"]):
        lines.append(f"--add-codec={codec}")
    for codec in ["iLBC", "speex", "GSM"]:
        lines.append(f"--dis-codec={codec}")

    # Audio settings
    if audio.get("channels", 1) == 2:
        lines.append("--stereo")

    # Audio device selection is handled via ALSA default device
    # (set in /etc/asound.conf or ~/.asoundrc) rather than pjsua --capture-dev/--playback-dev,
    # because pjsua's internal device IDs don't map directly to ALSA card numbers.

    # Play files for ready/error tones
    if READY_WAV.exists():
        lines.append(f"--play-file={READY_WAV}")
    if ERROR_WAV.exists():
        lines.append(f"--play-file={ERROR_WAV}")

    # STUN servers
    if sip.get("stun"):
        lines.append(f"--stun-srv={sip['stun']}")
    if sip.get("stun2"):
        lines.append(f"--stun-srv={sip['stun2']}")

    # Accounts (supports multiple)
    accounts = sip.get("accounts", [])
    if not accounts:
        # Single account from flat config (backward compat)
        accounts = [sip]

    first_account = True
    for account in accounts:
        if not account.get("username"):
            continue

        if not first_account:
            lines.append("--next-account")
        first_account = False

        username = account["username"]
        realm = account.get("realm", "")
        registrar = account.get("registrar") or account.get("proxy") or realm
        transport = account.get("transport", "tls")

        lines.append(f"--id=sip:{username}@{realm}")
        lines.append(f"--registrar=sip:{registrar}")
        lines.append(f"--realm={realm}")
        lines.append(f"--username={username}")
        # Password wrapped in double quotes for pjsua config file format.
        # Note: passwords containing double quotes will break pjsua parsing —
        # this is a known pjsua config file format limitation.
        password = account.get("password", "")
        lines.append(f'"--password={password}"')

        # Proxies
        if account.get("proxy"):
            lines.append(f"--proxy=sip:{account['proxy']};transport={transport}")
        if account.get("proxy2"):
            lines.append(f"--proxy=sip:{account['proxy2']};transport={transport}")

        lines.append(f"--use-{transport}")

        # TLS + SRTP
        if transport == "tls":
            keying = account.get("keying", 0)
            if keying:
                lines.append("--use-srtp=2")
                lines.append(f"--srtp-keying={keying - 1}")
            lines.append("--tls-ca-file=/etc/ssl/certs/ca-certificates.crt")
            lines.append("--tls-verify-server")

        lines.append(f"--reg-timeout={account.get('reg_timeout', 600)}")

    return "\n".join(lines) + "\n"


def write_config() -> Path:
    """Write pjsua config file and return its path."""
    try:
        PJSUA_CONF.parent.mkdir(parents=True, exist_ok=True)
        PJSUA_CONF.write_text(generate_config())
        logger.info("pjsua config written to %s", PJSUA_CONF)
    except PermissionError:
        logger.warning("Cannot write pjsua config to %s (check permissions on %s)", PJSUA_CONF, PJSUA_CONF.parent)
    return PJSUA_CONF


def get_device_string() -> list[str]:
    """Build pjsua audio device arguments.

    Resolves ALSA device IDs and sets jitter buffer based on connection type.
    """
    audio = get_section("audio")
    args = []

    # Audio device selection is handled via ALSA default device (/etc/asound.conf)
    # rather than pjsua --capture-dev/--playback-dev, because pjsua's internal
    # device IDs don't map directly to ALSA card numbers.

    if audio.get("capture_latency"):
        args.append(f"--capture-lat={audio['capture_latency']}")
    if audio.get("playback_latency"):
        args.append(f"--playback-lat={audio['playback_latency']}")
    if audio.get("period_size"):
        pass  # args.append(f"--period-size={audio['period_size']}")  # removed for pjsip 2.14

    # Jitter buffer — tighter for wired, wider for WiFi
    if audio.get("wifi_mode"):
        args.extend(["--jb-max-size=720"])
    else:
        args.extend(["--jb-max-size=360"])

    return args


class PjsuaProcess:
    """Manages the pjsua subprocess lifecycle.

    Infinite restart loop on unexpected exit, RT priority 99.
    """

    def __init__(self):
        self._process: Optional[asyncio.subprocess.Process] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._stopping = False
        self._lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def pid(self) -> Optional[int]:
        return self._process.pid if self.running else None

    async def start(self) -> None:
        async with self._lock:
            await self._start_unlocked()

    async def _start_unlocked(self) -> None:
        if self.running:
            logger.warning("pjsua already running (pid %d)", self._process.pid)
            return

        self._stopping = False
        write_config()
        device_args = get_device_string()

        # Launch with RT priority 99 via chrt
        cmd = [
            "/usr/bin/chrt", "-r", "99",
            PJSUA_BIN,
            f"--config-file={PJSUA_CONF}",
            # "--no-wav-loop",  # removed for pjsip 2.14
            "--thread-cnt=3",
        ] + device_args

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except FileNotFoundError:
            # Development mode — pjsua not installed
            logger.warning("pjsua binary not found at %s, running in stub mode", PJSUA_BIN)
            return

        try:
            PID_FILE.parent.mkdir(parents=True, exist_ok=True)
            PID_FILE.write_text(str(self._process.pid))
        except PermissionError:
            logger.warning("Cannot write PID file %s (non-fatal)", PID_FILE)
        logger.info("pjsua started (pid %d)", self._process.pid)

        # Monitor for unexpected exits
        self._monitor_task = asyncio.create_task(self._monitor())

    async def stop(self) -> None:
        async with self._lock:
            await self._stop_unlocked()

    async def _stop_unlocked(self) -> None:
        if not self.running:
            return

        self._stopping = True

        if self._monitor_task:
            self._monitor_task.cancel()

        self._process.send_signal(signal.SIGTERM)
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5)
        except asyncio.TimeoutError:
            self._process.kill()
            await self._process.wait()

        logger.info("pjsua stopped")
        self._process = None
        PID_FILE.unlink(missing_ok=True)

    async def restart(self) -> None:
        """Restart pjsua process."""
        async with self._lock:
            await self._stop_unlocked()
            await self._start_unlocked()

    async def _monitor(self) -> None:
        """Restart pjsua if it exits unexpectedly (sleep 2s, then restart)."""
        await self._process.wait()
        if self._stopping:
            return
        code = self._process.returncode
        if code == 127:
            logger.error("pjsua binary not found — install pjsua and restart the service")
            self._process = None
            return
        logger.warning("pjsua exited (code %d), restarting in 2s", code)
        self._process = None
        await asyncio.sleep(2)
        await self.start()


# Singleton
pjsua = PjsuaProcess()
