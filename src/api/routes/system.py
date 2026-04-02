"""System endpoints — status, network, display, AES67, WiFi, reboot, factory reset."""

import asyncio
import hashlib
import logging
import os
import socket
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

# Device lock state — locked on boot, unlocked with PIN for the session
_device_unlocked = False


@router.post("/unlock")
async def unlock_device(body: dict):
    """Unlock device with PIN code. Stays unlocked until reboot."""
    global _device_unlocked
    pin = body.get("pin", "")
    pin_hash = hashlib.sha256(pin.encode()).hexdigest()
    security = get_section("security")
    stored_hash = security.get("device_pin_hash", "")
    if not stored_hash:
        # No PIN configured — always unlocked
        _device_unlocked = True
        return {"unlocked": True}
    if pin_hash == stored_hash:
        _device_unlocked = True
        return {"unlocked": True}
    return JSONResponse(status_code=403, content={"unlocked": False, "error": "Invalid PIN"})


@router.get("/lock-status")
async def lock_status():
    """Check if device is locked."""
    security = get_section("security")
    has_pin = bool(security.get("device_pin_hash", ""))
    return {"locked": has_pin and not _device_unlocked, "has_pin": has_pin}


def _get_ip_addresses() -> dict[str, str]:
    """Get IP addresses for all active network interfaces."""
    import socket
    import fcntl
    import struct
    ips = {}
    for iface in ("bond0", "eth0", "wlan0"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            addr = fcntl.ioctl(s.fileno(), 0x8915,  # SIOCGIFADDR
                               struct.pack('256s', iface.encode()))
            ips[iface] = socket.inet_ntoa(addr[20:24])
        except (OSError, IOError):
            pass
    return ips


@router.get("/status")
async def system_status():
    temp = "unknown"
    temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if temp_path.exists():
        temp = f"{int(temp_path.read_text().strip()) / 1000:.1f}C"

    uptime = Path("/proc/uptime").read_text().split()[0] if Path("/proc/uptime").exists() else "0"
    hw = get_hardware_info()
    ips = _get_ip_addresses()

    # Public IP via STUN-discovered address or external service
    public_ip = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        public_ip = s.getsockname()[0]
        s.close()
        # If it's a private IP, it's behind NAT — try to get real public IP
        if public_ip.startswith(("10.", "172.", "192.168.")):
            import urllib.request
            public_ip = urllib.request.urlopen("https://api.ipify.org", timeout=3).read().decode().strip()
    except Exception:
        pass

    # WiFi signal strength from /proc/net/wireless
    wifi_signal = None
    try:
        wireless = Path("/proc/net/wireless").read_text()
        for line in wireless.splitlines():
            if "wlan0" in line:
                parts = line.split()
                wifi_signal = int(float(parts[3]))  # signal level in dBm
                break
    except Exception:
        pass

    # Active bond interface
    active_interface = None
    try:
        bond_status = Path("/proc/net/bonding/bond0").read_text()
        for line in bond_status.splitlines():
            if "Currently Active Slave:" in line:
                active_interface = line.split(":")[1].strip()
                break
    except Exception:
        pass

    return {
        "cpu_temp": temp,
        "uptime_seconds": float(uptime),
        "hostname": get_section("network").get("hostname", "rtesip"),
        "serial": hw.get("serial", ""),
        "model": hw.get("model", ""),
        "ip_addresses": ips,
        "public_ip": public_ip,
        "wifi_signal": wifi_signal,
        "active_interface": active_interface,
    }


@router.get("/config")
async def get_all_config():
    return load()


@router.put("/config")
async def update_config(sections: dict):
    """Update one or more config sections (e.g. { security: {...} })."""
    from src.config.system import apply_firewall_config
    results = {}
    for section, values in sections.items():
        results[section] = update_section(section, values)
    # Apply firewall if security was updated
    if "security" in sections:
        await asyncio.to_thread(apply_firewall_config)
    return results


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

_system_action_in_progress = False


@router.post("/reboot")
async def reboot():
    global _system_action_in_progress
    if _system_action_in_progress:
        return {"status": "action already in progress"}
    _system_action_in_progress = True
    subprocess.Popen(["sudo", "systemctl", "reboot"])
    return {"status": "rebooting"}


@router.post("/restart-services")
async def restart_services():
    subprocess.Popen(["sudo", "systemctl", "restart", "rtesip"])
    return {"status": "restarting"}


@router.post("/shutdown")
async def shutdown():
    global _system_action_in_progress
    if _system_action_in_progress:
        return {"status": "action already in progress"}
    _system_action_in_progress = True
    subprocess.Popen(["sudo", "systemctl", "poweroff"])
    return {"status": "shutting down"}


@router.post("/factory-reset")
async def do_factory_reset():
    global _system_action_in_progress
    if _system_action_in_progress:
        return {"status": "action already in progress"}
    _system_action_in_progress = True
    await asyncio.to_thread(factory_reset)
    subprocess.Popen(["sudo", "shutdown", "-r", "+0", "rtesip factory reset"])
    return {"status": "reset complete, rebooting"}
