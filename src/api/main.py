"""FastAPI application — single process serving API, WebSocket, and static files."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.routes import sip, audio, system, contacts, update
from src.api.ws import router as ws_router, connect_telnet, start_meters, stop_meters
from src.sip.pjsua_manager import pjsua
from src.config.system import apply_performance_governor
from src.config.settings import get_section
from src.audio.mixer import discover_mixers, toggle_phantom_power, init_hifi_xlr

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("rtesip starting")

    # Performance governor
    apply_performance_governor()

    # Initialize audio hardware state (phantom power, HiFiBerry XLR)
    await _init_audio_hardware()

    # Start pjsua
    await pjsua.start()

    # Connect to pjsua telnet CLI (with retry)
    asyncio.create_task(connect_telnet())

    # Start live audio metering
    asyncio.create_task(start_meters())

    yield

    logger.info("rtesip shutting down")
    await stop_meters()
    await pjsua.stop()


async def _init_audio_hardware() -> None:
    """Initialize audio hardware state on startup — phantom power, HiFiBerry XLR."""
    try:
        audio = get_section("audio")
        mixers = discover_mixers()
        hifi_xlr_cards = mixers.get("hifi_xlr", [])

        # Initialize HiFiBerry XLR boards (balanced inputs, headphone amp)
        if hifi_xlr_cards:
            init_hifi_xlr(hifi_xlr_cards)
            logger.info("HiFiBerry XLR initialized on cards: %s", hifi_xlr_cards)

        # Apply phantom power state from config
        if hifi_xlr_cards:
            phantom = audio.get("phantom_power", False)
            toggle_phantom_power(hifi_xlr_cards, phantom)
            logger.info("Phantom power %s on cards: %s", "enabled" if phantom else "disabled", hifi_xlr_cards)
    except Exception as e:
        logger.warning("Audio hardware init failed (non-fatal): %s", e)


app = FastAPI(title="rtesip", version="0.1.0", lifespan=lifespan)

# API routes
app.include_router(sip.router, prefix="/api/sip", tags=["sip"])
app.include_router(audio.router, prefix="/api/audio", tags=["audio"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(contacts.router, prefix="/api/contacts", tags=["contacts"])
app.include_router(update.router, prefix="/api/update", tags=["update"])

# WebSocket
app.include_router(ws_router)

# Serve frontend (React SPA)
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
