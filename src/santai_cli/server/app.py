"""FastAPI application factory for the headless Santai API server."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_server_app(token: str | None = None) -> FastAPI:
    """Create and configure the headless FastAPI server application.

    Parameters
    ----------
    token:
        Optional bearer token for API authentication.
        When ``None``, all requests are allowed.
    """
    app = FastAPI(
        title="Santai Server",
        description="Headless API for Santai project operations",
        docs_url="/docs",
        openapi_url="/openapi.json",
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
