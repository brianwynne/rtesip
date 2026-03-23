"""System endpoints — status, network, display, AES67, WiFi, reboot, factory reset."""

import subprocess
from pathlib import Path

from fastapi import APIRouter

from src.config.settings import get_section, update_section, load, get_hardware_info
from src.config.system import (
    apply_network_config, apply_wifi_config, apply_8021x_config,
    apply_timezone, apply_ntp_config, apply_ptp_config,
    apply_aes67_config, apply_boot_config, factory_reset,
)

router = APIRouter()


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
    apply_network_config()
    return result


# --- WiFi ---

@router.get("/wifi")
async def get_wifi():
    return get_section("wifi")


@router.put("/wifi")
async def update_wifi(settings: dict):
    result = update_section("wifi", settings)
    apply_wifi_config()
    if "enable_8021x" in settings:
        apply_8021x_config()
    return result


# --- Display ---

@router.get("/display")
async def get_display():
    return get_section("display")


@router.put("/display")
async def update_display(settings: dict):
    result = update_section("display", settings)
    apply_boot_config()
    return result


# --- AES67 ---

@router.get("/aes67")
async def get_aes67():
    return get_section("aes67")


@router.put("/aes67")
async def update_aes67(settings: dict):
    result = update_section("aes67", settings)
    apply_aes67_config()
    if "ptp_clock" in settings:
        apply_ptp_config()
    return result


# --- Timezone ---

@router.put("/timezone")
async def update_timezone(settings: dict):
    result = update_section("system", settings)
    apply_timezone()
    return result


# --- NTP ---

@router.put("/ntp")
async def update_ntp(settings: dict):
    result = update_section("network", settings)
    apply_ntp_config()
    return result


# --- System actions ---

@router.post("/reboot")
async def reboot():
    subprocess.Popen(["shutdown", "-r", "+0", "rtesip reboot"])
    return {"status": "rebooting"}


@router.post("/restart-services")
async def restart_services():
    subprocess.run(["systemctl", "restart", "rtesip"], timeout=10)
    return {"status": "restarting"}


@router.post("/factory-reset")
async def do_factory_reset():
    factory_reset()
    return {"status": "reset complete, rebooting"}
