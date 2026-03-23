"""API key authentication dependency."""

import logging

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

from src.config.settings import get_section

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Paths exempt from API key auth (relative to mounted prefix)
_PUBLIC_PATHS = {"/api/system/status"}


async def require_api_key(
    request: Request,
    api_key: str | None = Depends(_api_key_header),
) -> None:
    """Validate X-API-Key header against the configured security.api_key."""
    if request.url.path in _PUBLIC_PATHS:
        return

    security = get_section("security")
    expected = security.get("api_key", "")
    if not expected:
        # No key configured — auth disabled
        return

    if not api_key or api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
