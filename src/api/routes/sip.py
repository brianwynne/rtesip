"""SIP account and call control endpoints."""

from fastapi import APIRouter

from src.config.settings import get_section, update_section
from src.sip.pjsua_manager import pjsua

router = APIRouter()


@router.get("/accounts")
async def get_accounts():
    sip = get_section("sip")
    return sip.get("accounts", [])


@router.put("/accounts")
async def update_accounts(accounts: list):
    update_section("sip", {"accounts": accounts})
    await pjsua.restart()
    return {"status": "updated", "count": len(accounts)}


@router.get("/settings")
async def get_sip_settings():
    return get_section("sip")


@router.put("/settings")
async def update_sip_settings(settings: dict):
    updated = update_section("sip", settings)
    await pjsua.restart()
    return updated


@router.get("/status")
async def sip_status():
    return {
        "running": pjsua.running,
        "pid": pjsua.pid,
    }


@router.post("/restart")
async def restart_sip():
    await pjsua.restart()
    return {"status": "restarted"}
