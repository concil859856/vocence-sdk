"""Account / billing / API-key types."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow")


class Account(_Base):
    """Snapshot of the caller's account state — ``GET /v1/account``."""

    user_id: str
    email: str | None = None
    name: str | None = None
    credits: int
    plan_code: str
    plan_status: str
    api_keys_count: int = 0


class ApiKey(_Base):
    """Metadata for one API key — secrets are never returned."""

    id: str
    name: str
    key_prefix: str
    tier: str
    rate_limit_rpm: int | None = None
    revoked_at: str | None = None
    last_used_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ApiKeyCreated(_Base):
    """Returned by ``POST /v1/account/keys``. ``plain_key`` is the **only
    time** the plaintext secret will ever be available — store it now."""

    key: ApiKey
    plain_key: str


class UsageEntry(_Base):
    """One row from ``GET /v1/account/usage`` — a past API call."""

    id: str
    endpoint: str
    provider: str | None = None
    status: str
    http_status: int | None = None
    credits_used: int = 0
    request_chars: int | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: str | None = None
