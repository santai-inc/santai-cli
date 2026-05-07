"""Pydantic request/response models for the Santai server API."""

from __future__ import annotations

from pydantic import BaseModel

# --- Init ---


class InitRequest(BaseModel):
    """Request body for POST /api/init."""

    path: str
    name: str | None = None


class InitResponse(BaseModel):
    """Response body for POST /api/init."""

    status: str = "ok"
    path: str


# --- Copy ---


class CopyRequest(BaseModel):
    """Request body for POST /api/copy."""

    source: str
    destination: str


class CopyResponse(BaseModel):
    """Response body for POST /api/copy."""

    status: str = "ok"
    destination: str


# --- Cherry-pick ---


class CherryPickRequest(BaseModel):
    """Request body for POST /api/cherry-pick."""

    source: str
    destination: str
    files: list[str]
    overwrite: bool = False


class CherryPickResponse(BaseModel):
    """Response body for POST /api/cherry-pick."""

    status: str = "ok"
    copied: list[str]


# --- Merge ---


class MergeRequest(BaseModel):
    """Request body for POST /api/merge."""

    primary: str
    secondary: str
    output: str


class MergeResponse(BaseModel):
    """Response body for POST /api/merge."""

    status: str = "ok"
    output: str
