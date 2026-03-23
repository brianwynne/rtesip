"""Push update endpoint — receives firmware from management server."""

import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from src.update.updater import apply_update, rollback, get_current_version, UPDATE_DIR

router = APIRouter()


@router.get("/version")
async def version():
    return get_current_version()


@router.post("/push")
async def push_update(
    image: UploadFile = File(...),
    version: str = Form(...),
    sha256: str = Form(...),
):
    """Receive a firmware image, verify, and apply to inactive partition."""
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    image_path = UPDATE_DIR / f"update-{version}.img"

    with open(image_path, "wb") as f:
        shutil.copyfileobj(image.file, f)

    result = await apply_update(image_path, version, sha256)

    # Clean up
    image_path.unlink(missing_ok=True)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/rollback")
async def rollback_update():
    result = rollback()
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
