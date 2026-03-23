"""Push-based A/B update system — receives update via API, verifies, applies."""

import hashlib
import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PARTITIONS = {"A": "/dev/mmcblk0p2", "B": "/dev/mmcblk0p3"}
BOOT_CONFIG = Path("/boot/cmdline.txt")
UPDATE_DIR = Path("/var/lib/rtesip/updates")
CURRENT_VERSION_FILE = Path("/var/lib/rtesip/version.json")


def get_current_version() -> dict:
    if CURRENT_VERSION_FILE.exists():
        return json.loads(CURRENT_VERSION_FILE.read_text())
    return {"version": "0.0.0", "partition": "A"}


def get_inactive_partition() -> str:
    current = get_current_version()
    return "B" if current.get("partition") == "A" else "A"


def verify_image(image_path: Path, expected_sha256: str) -> bool:
    """Verify downloaded image integrity."""
    sha256 = hashlib.sha256()
    with open(image_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    actual = sha256.hexdigest()
    if actual != expected_sha256:
        logger.error("Hash mismatch: expected %s, got %s", expected_sha256, actual)
        return False
    return True


def write_to_partition(image_path: Path, partition: str) -> bool:
    """Write update image to the inactive partition."""
    device = PARTITIONS[partition]
    logger.info("Writing %s to %s (%s)", image_path, partition, device)
    try:
        subprocess.run(
            ["dd", f"if={image_path}", f"of={device}", "bs=4M", "status=progress"],
            check=True,
            timeout=600,
        )
        subprocess.run(["sync"], check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Failed to write partition: %s", e)
        return False


def switch_boot_partition(partition: str, version: str) -> bool:
    """Update boot config to use the new partition."""
    device = PARTITIONS[partition]
    try:
        cmdline = BOOT_CONFIG.read_text()
        # Replace root= parameter
        parts = cmdline.split()
        new_parts = []
        for part in parts:
            if part.startswith("root="):
                new_parts.append(f"root={device}")
            else:
                new_parts.append(part)
        BOOT_CONFIG.write_text(" ".join(new_parts))

        # Record new version
        CURRENT_VERSION_FILE.write_text(json.dumps({
            "version": version,
            "partition": partition,
            "previous": get_current_version(),
        }, indent=2))

        logger.info("Boot switched to partition %s (v%s)", partition, version)
        return True
    except Exception as e:
        logger.error("Failed to switch boot: %s", e)
        return False


async def apply_update(image_path: Path, version: str, sha256: str) -> dict:
    """Full update flow: verify, write, switch boot."""
    if not verify_image(image_path, sha256):
        return {"success": False, "error": "Hash verification failed"}

    target = get_inactive_partition()

    if not write_to_partition(image_path, target):
        return {"success": False, "error": f"Failed to write to partition {target}"}

    if not switch_boot_partition(target, version):
        return {"success": False, "error": "Failed to switch boot config"}

    return {"success": True, "partition": target, "version": version, "reboot_required": True}


def rollback() -> dict:
    """Switch back to the previous partition."""
    current = get_current_version()
    previous = current.get("previous", {})
    if not previous:
        return {"success": False, "error": "No previous version to rollback to"}

    prev_partition = previous.get("partition", get_inactive_partition())
    switch_boot_partition(prev_partition, previous.get("version", "unknown"))
    return {"success": True, "partition": prev_partition, "reboot_required": True}
