"""Authentication middleware for the Santai API server."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, status

# Paths that skip authentication
PUBLIC_PATHS: set[str] = {
    "/api/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}


def create_auth_dependency(token: str | None) -> Any:
    """Create a FastAPI dependency that enforces bearer token auth.

    Parameters
    ----------
    token:
        The expected bearer token. When ``None``, authentication is
        disabled and all requests are allowed through.

    Returns
    -------
    A callable suitable for use as an app-level dependency.
    """

    async def verify_token(request: Request) -> None:
        # No token configured — allow all requests
        if token is None:
            return

        # Skip auth for public paths
        if request.url.path in PUBLIC_PATHS:
            return

        # Token is configured — require valid Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Expect "Bearer <token>" format
        parts = auth_header.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if parts[1] != token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return verify_token
