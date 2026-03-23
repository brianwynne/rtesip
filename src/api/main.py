"""FastAPI application — single process serving API, WebSocket, and static files."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.routes import sip, audio, system, contacts, update
from src.api.ws import router as ws_router, connect_telnet
from src.sip.pjsua_manager import pjsua
from src.config.system import apply_performance_governor

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

    # Start pjsua
    await pjsua.start()

    # Connect to pjsua telnet CLI (with retry)
    asyncio.create_task(connect_telnet())

    yield

    logger.info("rtesip shutting down")
    await pjsua.stop()


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
