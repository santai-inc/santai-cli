"""FastAPI application factory for the headless Santai API server."""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from santai_cli.server.auth import create_auth_dependency

logger = logging.getLogger("santai.server")


def create_server_app(token: str | None = None, host: str = "127.0.0.1") -> FastAPI:
    """Create and configure the headless FastAPI server application.

    Parameters
    ----------
    token:
        Optional bearer token for API authentication.
        When ``None``, all requests are allowed.
    host:
        The host the server will bind to. Used to emit a warning
        when binding to a non-localhost address without a token.
    """
    # Warn when binding to non-localhost without a token
    if host != "127.0.0.1" and host != "localhost" and token is None:
        logger.warning(
            "Server binding to %s without authentication token. "
            "Consider using --token or SANTAI_SERVER_TOKEN to secure the API.",
            host,
        )

    auth_dep = create_auth_dependency(token)

    app = FastAPI(
        title="Santai Server",
        description="Headless API for Santai project operations",
        docs_url="/docs",
        openapi_url="/openapi.json",
        dependencies=[Depends(auth_dep)],
    )

    # CORS middleware for API access from external clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}

    return app
