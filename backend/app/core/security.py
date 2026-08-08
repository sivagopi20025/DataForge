from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from backend.app.core.config import get_settings
from backend.app.core.rate_limit import enforce_rate_limit


def require_api_key(request: Request, x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Require an API key only when DATAFORGE_API_KEY is configured.

    This gives local development a zero-friction default while providing a
    deployment-ready protection point for generation, history, downloads, and
    admin APIs.
    """

    expected = get_settings().api_key
    enforce_rate_limit(request, token=x_api_key)
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid or missing API key", "code": "UNAUTHORIZED"},
        )
