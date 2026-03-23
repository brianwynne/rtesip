"""System configuration — network, WiFi, boot config, and factory reset.

Provides direct functions called by the API routes to apply system settings.
"""

import ipaddress
import logging
import re
import subprocess
from pathlib import Path

from src.config.settings import get_section, update_section, DATA_DIR

logger = logging.getLogger(__name__)


# --- Network ---

def apply_network_config() -> None:
    """Apply network settings — static IP or DHCP via dhcpcd."""
    network = get_section("network")

    # Build dhcpcd.conf
    base_conf = Path("/opt/rtesip/conf/dhcpcd.conf")
    if base_conf.exists():
        dhcpcd = base_conf.read_text()
    else:
        dhcpcd = ""

    if network["mode"] == "static" and network.get("address"):
        # Calculate CIDR prefix from netmask
        prefix = ipaddress.IPv4Network(f"0.0.0.0/{network['netmask']}", strict=False).prefixlen
        dhcpcd += f"\nstatic ip_address={network['address']}/{prefix}"
        dhcpcd += f"\nstatic routers={network['gateway']}"
        dns = network.get("dns1", "")
        if network.get("dns2"):
            dns += f" {network['dns2']}"
        dhcpcd += f"\nstatic domain_name_servers={dns}"

    Path("/etc/dhcpcd.conf").write_text(dhcpcd)

    if network.get("hostname"):
        Path("/etc/hostname").write_text(network["hostname"])
        subprocess.run(["hostname", network["hostname"]], timeout=5)

    subprocess.run(["systemctl", "restart", "dhcpcd"], timeout=30)


# --- WiFi ---

def apply_wifi_config() -> None:
    """Apply WiFi settings — wpa_supplicant config."""
    wifi = get_section("wifi")

    # Kill existing wpa_supplicant
    subprocess.run(["killall", "wpa_supplicant"], capture_output=True, timeout=5)

    if wifi.get("enabled") and wifi.get("ssid"):
        interface = wifi.get("interface", "wlan0")
        conf = (
            f"ctrl_interface=DIR=/run/wpa_supplicant GROUP=netdev\n"
            f"country={wifi.get('country', 'ie').lower()}\n"
            f"update_config=1\n"
            f"network={{\n"
            f"  ssid=\"{wifi['ssid']}\"\n"
            f"  scan_ssid=1\n"
            f"  key_mgmt=WPA-PSK\n"
            f"  psk=\"{wifi['psk']}\"\n"
            f"}}\n"
        )
        wpa_path = Path(f"/etc/wpa_supplicant/wpa_supplicant-{interface}.conf")
        wpa_path.write_text(conf)


# --- 802.1X ---

def apply_8021x_config() -> None:
    """Apply 802.1X wired authentication."""
    wifi = get_section("wifi")

    if wifi.get("enable_8021x"):
        conf = (
            f"ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n"
            f"ap_scan=0\n"
            f"network={{\n"
            f"  key_mgmt=IEEE8021X\n"
            f"  eap=PEAP\n"
            f"  identity=\"{wifi['8021x_user']}\"\n"
            f"  password=\"{wifi['8021x_password']}\"\n"
        )
        if wifi.get("8021x_peaplabel1"):
            conf += "  phase1=\"peaplabel=1\"\n"
        conf += (
            "  phase2=\"auth=MSCHAPV2\"\n"
            "  eapol_flags=0\n"
            "}\n"
        )
        Path("/etc/wpa_supplicant/wpa_supplicant-wired-eth0.conf").write_text(conf)
        subprocess.run(["systemctl", "enable", "wpa_supplicant-wired@eth0.service"], timeout=10)
        subprocess.run(["systemctl", "restart", "wpa_supplicant-wired@eth0.service"], timeout=10)
    else:
        subprocess.run(["systemctl", "disable", "wpa_supplicant-wired@eth0.service"],
                       capture_output=True, timeout=10)
        subprocess.run(["systemctl", "stop", "wpa_supplicant-wired@eth0.service"],
                       capture_output=True, timeout=10)


# --- Timezone (from updateTimezone block) ---

def apply_timezone() -> None:
    system = get_section("system")
    tz = system.get("timezone", "Europe/Dublin")
    subprocess.run(["timedatectl", "set-timezone", tz], timeout=10)


# --- Chrony/NTP (from updateChrony block) ---

def apply_ntp_config() -> None:
    """Update chrony NTP servers."""
    network = get_section("network")
    chrony_base = Path("/opt/rtesip/conf/chrony.conf")

    if Path("/etc/chrony/chrony.conf").exists():
        servers = ""
        for server in network.get("time_servers", "").strip().split("\n"):
            if server.strip():
                servers += f"server {server.strip()}\n"
        base = chrony_base.read_text() if chrony_base.exists() else ""
        Path("/etc/chrony/chrony.conf").write_text(servers + base)
        subprocess.run(["systemctl", "restart", "chrony"], timeout=10)


# --- PTP (from configurePTP block) ---

def apply_ptp_config() -> None:
    """Enable/disable PTP clock for AES67."""
    aes67 = get_section("aes67")
    if aes67.get("ptp_clock"):
        subprocess.run(["systemctl", "enable", "ptp4l.service"], timeout=10)
        subprocess.run(["systemctl", "start", "ptp4l.service"], timeout=10)
    else:
        subprocess.run(["systemctl", "disable", "ptp4l.service"], capture_output=True, timeout=10)
        subprocess.run(["systemctl", "stop", "ptp4l.service"], capture_output=True, timeout=10)


# --- AES67 (from configureAES67 block) ---

def apply_aes67_config() -> None:
    """Enable/disable AES67 Ravenna daemon."""
    aes67 = get_section("aes67")
    if aes67.get("enabled"):
        subprocess.run(["systemctl", "enable", "avahi-daemon.service"], timeout=10)
        subprocess.run(["systemctl", "restart", "avahi-daemon.service"], timeout=10)
        subprocess.run(["systemctl", "enable", "aes67.service"], timeout=10)
        subprocess.run(["systemctl", "restart", "aes67.service"], timeout=10)
    else:
        # Check if AES67 device is in use before disabling
        audio = get_section("audio")
        if "AES67" in audio.get("input", "") or "AES67" in audio.get("output", ""):
            # Switch audio back to USB
            update_section("audio", {"input": "USB", "output": "USB"})

        subprocess.run(["systemctl", "disable", "aes67.service"], capture_output=True, timeout=10)
        subprocess.run(["systemctl", "stop", "aes67.service"], capture_output=True, timeout=10)
        subprocess.run(["systemctl", "disable", "avahi-daemon.service"], capture_output=True, timeout=10)
        subprocess.run(["systemctl", "stop", "avahi-daemon.service"], capture_output=True, timeout=10)


# --- Boot config (from reconfigureBoot block) ---

def apply_boot_config() -> None:
    """Update /boot/config.txt for display and audio hat overlays.

    Manages dtoverlay lines for display and audio hat configuration.
    """
    display = get_section("display")
    system = get_section("system")

    boot_config = Path("/boot/config.txt")
    if not boot_config.exists():
        return

    config = boot_config.read_text()

    # Clear auto-config section
    patterns = [
        r'dtoverlay=pitft35.+', r'dtoverlay=piscreen.*', r'lcd_rotate=.+',
        r'dtoverlay=hifiberry.+', r'force_eeprom_read=.+', r'dtoverlay=vc4-.+',
        r'# rtesip Automatic Configuration #',
    ]
    for pattern in patterns:
        config = re.sub(pattern, "", config)

    config = config.strip() + "\n\n# rtesip Automatic Configuration #\n"

    # Display overlay
    if display["mode"] != "none":
        dtype = display.get("type", "7official")
        rotation = display.get("rotation", 0)

        if dtype == "35adafruit":
            rot = 270 if rotation else 90
            config += f"dtoverlay=pitft35-resistive,rotate={rot},swapxy=1\n"
        elif dtype == "35generic":
            config += f"dtoverlay=piscreen{'rotate=180' if rotation else ''}\n"
            if rotation:
                config += "lcd_rotate=2\n"
        elif dtype == "7official" and rotation:
            config += "lcd_rotate=2\n"

        # KMS/FKMS driver selection
        if dtype in ("35adafruit", "35generic"):
            config += "dtoverlay=vc4-kms-v3d\n"
        else:
            config += "dtoverlay=vc4-fkms-v3d\n"

    # HiFiBerry overlay
    hifi = system.get("hifi_berry", "none")
    if hifi != "none":
        config += f"dtoverlay=hifiberry-{hifi}\n"
        config += "force_eeprom_read=0\n"

    boot_config.write_text(config)
    subprocess.run(["sync"], timeout=5)


# --- Performance governor ---

def apply_performance_governor() -> None:
    """Set CPU to performance mode."""
    governor_path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    if governor_path.exists():
        governor_path.write_text("performance")


# --- Factory reset ---

def factory_reset() -> None:
    """Reset all config to defaults."""
    from src.config.settings import DEFAULTS, save

    # Preserve product info
    current = get_section("base")
    new_config = {k: dict(v) for k, v in DEFAULTS.items()}
    new_config["base"]["product_name"] = current.get("product_name", "rtesip")
    new_config["base"]["product_code"] = current.get("product_code", "")
    new_config["base"]["unit_description"] = current.get("unit_description", "")
    new_config["base"]["language"] = current.get("language", "english")

    save(new_config)

    # Reset system config
    Path("/etc/hostname").write_text("rtesip")
    subprocess.run(["hostname", "rtesip"], timeout=5)

    apply_ntp_config()
    apply_network_config()

    # Disable optional services
    for svc in ["wpa_supplicant-wired@eth0", "aes67", "avahi-daemon", "ptp4l"]:
        subprocess.run(["systemctl", "disable", f"{svc}.service"], capture_output=True, timeout=10)
        subprocess.run(["systemctl", "stop", f"{svc}.service"], capture_output=True, timeout=10)

    logger.info("Factory reset complete")
