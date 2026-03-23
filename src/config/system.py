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

_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$")


def _sanitize_quoted(value: str) -> str:
    """Strip characters that could escape wpa_supplicant quoted strings."""
    return value.replace('"', '').replace('\\', '').replace('\n', '').replace('\r', '')


def _validate_hostname(name: str) -> str:
    """Validate and return a safe hostname, or fall back to 'rtesip'."""
    name = name.strip()
    if _HOSTNAME_RE.match(name):
        return name
    logger.warning("Invalid hostname '%s', falling back to 'rtesip'", name)
    return "rtesip"


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
        hostname = _validate_hostname(network["hostname"])
        Path("/etc/hostname").write_text(hostname)
        subprocess.run(["hostname", hostname], timeout=5)

    subprocess.run(["systemctl", "restart", "dhcpcd"], timeout=30)


# --- WiFi ---

def apply_wifi_config() -> None:
    """Apply WiFi settings — wpa_supplicant config."""
    wifi = get_section("wifi")

    # Kill existing wpa_supplicant
    subprocess.run(["killall", "wpa_supplicant"], capture_output=True, timeout=5)

    if wifi.get("enabled") and wifi.get("ssid"):
        interface = wifi.get("interface", "wlan0")
        ssid = _sanitize_quoted(wifi["ssid"])
        psk = _sanitize_quoted(wifi.get("psk", ""))
        conf = (
            f"ctrl_interface=DIR=/run/wpa_supplicant GROUP=netdev\n"
            f"country={wifi.get('country', 'ie').lower()}\n"
            f"update_config=1\n"
            f"network={{\n"
            f"  ssid=\"{ssid}\"\n"
            f"  scan_ssid=1\n"
            f"  key_mgmt=WPA-PSK\n"
            f"  psk=\"{psk}\"\n"
            f"}}\n"
        )
        wpa_path = Path(f"/etc/wpa_supplicant/wpa_supplicant-{interface}.conf")
        wpa_path.write_text(conf)


# --- WiFi Scan ---

def scan_wifi_networks(interface: str = "wlan0", timeout: int = 10) -> list[dict]:
    """Scan for available WiFi networks using wpa_cli.

    Returns list of dicts with ssid, bssid, signal, frequency, flags.
    Same approach as the original scanWiFi block — launches wpa_supplicant
    with a scan config if needed, runs scan, parses results.
    """
    networks = []

    # Ensure interface is up
    subprocess.run(["ip", "link", "set", interface, "up"],
                   capture_output=True, timeout=5)

    # Trigger scan
    try:
        subprocess.run(
            ["wpa_cli", "-i", interface, "scan"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("WiFi scan trigger failed: %s", e)
        return networks

    # Wait for scan results (poll up to timeout seconds)
    import time
    best_results = []
    for _ in range(timeout):
        time.sleep(1)
        try:
            result = subprocess.run(
                ["wpa_cli", "-i", interface, "scan_results"],
                capture_output=True, text=True, timeout=5,
            )
            lines = result.stdout.strip().split("\n")
            # First line is header: bssid / frequency / signal / flags / ssid
            if len(lines) > len(best_results):
                best_results = lines
        except (subprocess.TimeoutExpired, FileNotFoundError):
            break

    # Parse results (skip header line)
    seen_ssids = set()
    for line in best_results[1:]:
        parts = line.split("\t")
        if len(parts) >= 5:
            ssid = parts[4].strip()
            if not ssid or ssid in seen_ssids or "\x00" in ssid:
                continue
            seen_ssids.add(ssid)
            networks.append({
                "bssid": parts[0],
                "frequency": int(parts[1]) if parts[1].isdigit() else 0,
                "signal": int(parts[2]) if parts[2].lstrip("-").isdigit() else 0,
                "flags": parts[3],
                "ssid": ssid,
                "security": "WPA" if "WPA" in parts[3] else "Open",
            })

    # Sort by signal strength (strongest first)
    networks.sort(key=lambda n: n["signal"], reverse=True)
    logger.info("WiFi scan found %d networks", len(networks))
    return networks


# --- 802.1X ---

def apply_8021x_config() -> None:
    """Apply 802.1X wired authentication."""
    wifi = get_section("wifi")

    if wifi.get("enable_8021x"):
        identity = _sanitize_quoted(wifi.get("8021x_user", ""))
        password = _sanitize_quoted(wifi.get("8021x_password", ""))
        conf = (
            f"ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n"
            f"ap_scan=0\n"
            f"network={{\n"
            f"  key_mgmt=IEEE8021X\n"
            f"  eap=PEAP\n"
            f"  identity=\"{identity}\"\n"
            f"  password=\"{password}\"\n"
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


# --- Firewall ---

def apply_firewall_config() -> None:
    """Apply firewall settings — enable/disable ufw, configure trusted networks.

    Reads security.firewall_enabled and security.trusted_networks from config.
    """
    security = get_section("security")
    enabled = security.get("firewall_enabled", True)
    trusted = security.get("trusted_networks", "")

    try:
        if enabled:
            # Enable ufw
            subprocess.run(["ufw", "--force", "enable"],
                           capture_output=True, timeout=10)

            # Reset to defaults
            subprocess.run(["ufw", "default", "deny", "incoming"],
                           capture_output=True, timeout=10)
            subprocess.run(["ufw", "default", "allow", "outgoing"],
                           capture_output=True, timeout=10)

            # Always allow SSH and HTTP
            subprocess.run(["ufw", "allow", "22/tcp"],
                           capture_output=True, timeout=10)
            subprocess.run(["ufw", "allow", "80/tcp"],
                           capture_output=True, timeout=10)

            # AES67 multicast
            subprocess.run(["ufw", "allow", "52002/udp"],
                           capture_output=True, timeout=10)

            # Add trusted networks — allow all traffic from these CIDRs
            for line in trusted.strip().split("\n"):
                cidr = line.strip()
                if cidr and re.match(r'^[0-9./]+$', cidr):
                    subprocess.run(
                        ["ufw", "allow", "from", cidr],
                        capture_output=True, timeout=10,
                    )
                    logger.info("Firewall: trusted network %s", cidr)

            logger.info("Firewall enabled with %d trusted networks",
                        len([l for l in trusted.strip().split("\n") if l.strip()]))
        else:
            subprocess.run(["ufw", "--force", "disable"],
                           capture_output=True, timeout=10)
            logger.info("Firewall disabled")

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("Firewall configuration failed: %s", e)


# --- Performance governor ---

def apply_performance_governor() -> None:
    """Set CPU to performance mode. Non-fatal if no permission (runs as non-root)."""
    try:
        for gov in Path("/sys/devices/system/cpu/").glob("cpu*/cpufreq/scaling_governor"):
            gov.write_text("performance")
        logger.info("CPU governor set to performance")
    except PermissionError:
        logger.info("CPU governor: no permission (set via rc.local or install script instead)")
    except Exception as e:
        logger.warning("CPU governor failed: %s", e)


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
