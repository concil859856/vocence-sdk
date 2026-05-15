"""Agent / agent-binding types."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow")


class AgentConfig(_Base):
    """Inner ``config`` block of an agent record."""

    purpose: str = ""
    system_prompt: str = ""
    knowledge: str = ""
    voice: str | None = None
    language: str | None = None
    llm_model: str | None = None
    temperature: float | None = 0.6
    enabled_tools: list[str] | None = None
    goal: str | None = None
    success_metric: str | None = None
    max_iterations: int | None = None


class Agent(_Base):
    """Full agent record returned by ``GET /v1/agents/{id}`` and the
    create / patch endpoints."""

    id: str
    type: str
    status: str
    name: str
    config: AgentConfig
    created_at: str
    updated_at: str
    last_run_at: str | None = None
    run_count: int = 0
    custom_tools: list[Any] | None = None


class AgentSummary(_Base):
    """Compact agent entry returned by ``GET /v1/agents`` — id + name only."""

    id: str
    name: str


class AgentBinding(_Base):
    """Simple ack returned by ``POST/DELETE /v1/agents/{id}/tools/{tool_id}``."""

    ok: bool
