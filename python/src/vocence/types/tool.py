"""Custom-tool (user-defined webhook) types."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow")


class CustomTool(_Base):
    """Returned by ``GET /v1/agent-tools`` and friends.

    ``auth_secret`` is never returned by the server. ``has_secret`` tells
    you whether one was stored.
    """

    id: str
    name: str
    description: str
    parameters: dict[str, Any]
    endpoint_url: str
    method: str
    auth_type: str
    auth_header_name: str | None = None
    has_secret: bool
    timeout_ms: int
    created_at: str | None = None
    updated_at: str | None = None
