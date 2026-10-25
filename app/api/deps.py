"""Control plane authentication dependencies.

Per Section 2.2 of agent.md:
Control-plane endpoints that change state require a shared-secret header ('X-Control-Secret').
"""

from __future__ import annotations

from typing import Any

try:
    from fastapi import Header, HTTPException, status
except ImportError:
    class HTTPException(Exception):  # type: ignore[no-redef]
        def __init__(self, status_code: int, detail: str) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    def Header(default: Any = ..., *, alias: str | None = None) -> Any:  # type: ignore[no-redef]
        return default

    class status:  # type: ignore[no-redef]
        HTTP_401_UNAUTHORIZED = 401


from app.core.config import get_settings


async def verify_control_secret(x_control_secret: str = Header(..., alias="X-Control-Secret")) -> str:
    """Validate that the request carries the configured control secret."""
    settings = get_settings()
    if x_control_secret != settings.CONTROL_PLANE_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Control-Secret header",
        )
    return x_control_secret
