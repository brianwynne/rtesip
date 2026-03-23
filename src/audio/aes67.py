"""AES67/Ravenna daemon communication.

Talks to the Ravenna daemon's HTTP API on port 8081.
"""

import json
import logging
import subprocess
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DAEMON_PORT = 8081


def _get_local_ip() -> str:
    """Get local IP for Ravenna daemon communication."""
    try:
        result = subprocess.run(
            ["ip", "-json", "address"],
            capture_output=True, text=True, timeout=5,
        )
        interfaces = json.loads(result.stdout)
        for iface in interfaces:
            if iface["ifname"].startswith(("eth", "en")):
                for addr in iface.get("addr_info", []):
                    if addr["family"] == "inet":
                        return addr["local"]
    except Exception as e:
        logger.error("Failed to get local IP: %s", e)
    return "127.0.0.1"


async def daemon_request(path: str, method: str = "GET", data: Optional[str] = None) -> Optional[dict]:
    """Send request to Ravenna daemon API.

    """
    local_ip = _get_local_ip()
    url = f"http://{local_ip}:{DAEMON_PORT}{path}"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            if method == "GET":
                resp = await client.get(url)
            elif method == "PUT":
                resp = await client.put(url, content=data, headers={"Content-Type": "application/json"})
            elif method == "DELETE":
                resp = await client.delete(url)
            else:
                resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})

            if resp.status_code == 200:
                return resp.json()
            logger.warning("Ravenna API %s returned %d", path, resp.status_code)
    except Exception as e:
        logger.error("Ravenna API error for %s: %s", path, e)
    return None


async def get_ptp_status() -> dict:
    """Check PTP clock status — must be 'locked' before AES67 audio works."""
    result = await daemon_request("/api/ptp/status")
    if result:
        return result
    return {"status": "unknown"}


async def is_clock_locked() -> bool:
    status = await get_ptp_status()
    return status.get("status") == "locked"


async def get_config() -> Optional[dict]:
    return await daemon_request("/api/config")


async def get_sources() -> list:
    """Get local AES67 sources."""
    result = await daemon_request("/api/sources")
    if result and "sources" in result:
        return result["sources"]
    return []


async def get_remote_sources() -> list:
    """Browse available remote AES67 sources on the network."""
    result = await daemon_request("/api/browse/sources/all")
    if result and "remote_sources" in result:
        return result["remote_sources"]
    return []


async def get_sinks() -> list:
    result = await daemon_request("/api/sinks")
    if result and "sinks" in result:
        return result["sinks"]
    return []


async def update_source(settings: dict) -> Optional[dict]:
    """Create or update local AES67 source."""
    sources = await get_sources()
    if sources:
        source = sources[0]
        needs_update = False
        for key, value in settings.items():
            if source.get(key) != value:
                source[key] = value
                needs_update = True
        if needs_update:
            await daemon_request("/api/source/0", "PUT", json.dumps(source))
        return source
    else:
        # Create new source with defaults
        config = await get_config()
        sample_rate = config.get("sample_rate", 48000) if config else 48000
        new_source = {
            "enabled": True,
            "name": "SIP Rec",
            "io": "Audio Device",
            "codec": "L24",
            "max_samples_per_packet": sample_rate // 1000,
            "ttl": 15,
            "payload_type": 98,
            "dscp": 34,
            "refclk_ptp_traceable": False,
            "map": [0, 1],
        }
        new_source.update(settings)
        await daemon_request("/api/source/0", "PUT", json.dumps(new_source))
        return new_source


async def update_sink(sink_id: str, remote_sources: list, channel_map: list = None) -> Optional[dict]:
    """Connect to a remote AES67 source."""
    if channel_map is None:
        channel_map = [0, 1]

    target = None
    for source in remote_sources:
        if source.get("id") == sink_id:
            target = source
            break

    if not target:
        return None

    config = await get_config()
    sample_rate = config.get("sample_rate", 48000) if config else 48000

    # Remove existing sink and create new one
    await daemon_request("/api/sink/0", "DELETE")

    sink_data = {
        "name": target["name"],
        "io": "Audio Device",
        "delay": 2 * sample_rate // 1000,
        "use_sdp": True,
        "source": "",
        "sdp": target["sdp"],
        "ignore_refclk_gmid": True,
        "map": channel_map,
    }
    await daemon_request("/api/sink/0", "PUT", json.dumps(sink_data))
    return target


def has_aes67() -> bool:
    """Check if AES67 kernel module is available."""
    try:
        result = subprocess.run(["uname", "-r"], capture_output=True, text=True, timeout=5)
        kernel = result.stdout.strip()
        return Path(f"/usr/local/aes67/MergingRavennaALSA.{kernel}.ko").exists()
    except Exception:
        return False
