"""System endpoints — status, network, display, AES67, WiFi, reboot, factory reset."""

import asyncio
import logging
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

from src.api.auth import require_api_key
from src.config.settings import get_section, update_section, load, get_hardware_info
from src.config.system import (
    apply_network_config, apply_wifi_config, apply_8021x_config,
    apply_timezone, apply_ntp_config, apply_ptp_config,
    apply_aes67_config, apply_boot_config, factory_reset,
)

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/status")
async def system_status():
    temp = "unknown"
    temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if temp_path.exists():
        temp = f"{int(temp_path.read_text().strip()) / 1000:.1f}C"

    uptime = Path("/proc/uptime").read_text().split()[0] if Path("/proc/uptime").exists() else "0"
    hw = get_hardware_info()

    return {
        "cpu_temp": temp,
        "uptime_seconds": float(uptime),
        "hostname": get_section("network").get("hostname", "rtesip"),
        "serial": hw.get("serial", ""),
        "model": hw.get("model", ""),
    }


@router.get("/config")
async def get_all_config():
    return load()


# --- Network ---

@router.get("/network")
async def get_network():
    return get_section("network")


@router.put("/network")
async def update_network(settings: dict):
    result = update_section("network", settings)
    await asyncio.to_thread(apply_network_config)
    return result


# --- WiFi ---

@router.get("/wifi")
async def get_wifi():
    return get_section("wifi")


@router.get("/wifi/scan")
async def wifi_scan():
    """Scan for available WiFi networks."""
    from src.config.system import scan_wifi_networks
    networks = await asyncio.to_thread(scan_wifi_networks)
    return {"networks": networks}


@router.put("/wifi")
async def update_wifi(settings: dict):
    result = update_section("wifi", settings)
    await asyncio.to_thread(apply_wifi_config)
    if "enable_8021x" in settings:
        await asyncio.to_thread(apply_8021x_config)
    return result


# --- Display ---

@router.get("/display")
async def get_display():
    return get_section("display")


@router.put("/display")
async def update_display(settings: dict):
    result = update_section("display", settings)
    await asyncio.to_thread(apply_boot_config)
    return result


# --- AES67 ---

@router.get("/aes67")
async def get_aes67():
    return get_section("aes67")


@router.put("/aes67")
async def update_aes67(settings: dict):
    result = update_section("aes67", settings)
    await asyncio.to_thread(apply_aes67_config)
    if "ptp_clock" in settings:
        await asyncio.to_thread(apply_ptp_config)
    return result


# --- Timezone ---

@router.put("/timezone")
async def update_timezone(settings: dict):
    result = update_section("system", settings)
    await asyncio.to_thread(apply_timezone)
    return result


# --- NTP ---

@router.put("/ntp")
async def update_ntp(settings: dict):
    result = update_section("network", settings)
    await asyncio.to_thread(apply_ntp_config)
    return result


# --- System actions ---

@router.post("/reboot")
async def reboot():
    try:
        subprocess.Popen(["shutdown", "-r", "+0", "rtesip reboot"])
        return {"status": "rebooting"}
    except Exception as e:
        logger.error("Reboot failed: %s", e)
        return JSONResponse(status_code=500, content={"error": f"Reboot failed: {e}"})


@router.post("/restart-services")
async def restart_services():
    try:
        subprocess.run(["systemctl", "restart", "rtesip"], timeout=10)
        return {"status": "restarting"}
    except Exception as e:
        logger.error("Service restart failed: %s", e)
        return JSONResponse(status_code=500, content={"error": f"Service restart failed: {e}"})


@router.post("/factory-reset")
async def do_factory_reset():
    await asyncio.to_thread(factory_reset)
    subprocess.Popen(["shutdown", "-r", "+0", "rtesip factory reset"])
    return {"status": "reset complete, rebooting"}
