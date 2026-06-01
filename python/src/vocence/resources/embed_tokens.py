"""Embed-token management — mirrors
``/v1/agents/{agent_id}/embed-tokens/*`` on the developer API.

Embed tokens let you drop the ``<vocence-agent>`` widget on any
website without exposing your API key. Use:

    client = Vocence(api_key="voc_live_…")
    et = client.agents.embed_tokens("ag_123")
    created = et.create(
        label="staging-site",
        allowed_origins=["https://staging.example.com"],
        rate_limit_per_ip_per_hour=60,
        max_session_minutes=10,
    )
    print(created["plaintext"])  # save this — server NEVER returns it again
    print(created["embed_snippet"])  # paste-ready HTML

Listing returns metadata only — the plaintext is never re-issued.
"""

from __future__ import annotations

from typing import Any


def _create_body(**fields: Any) -> dict[str, Any]:
    """Drop ``None`` values so the server applies its defaults for
    anything the caller didn't specify (eg. ``rate_limit_per_ip_per_hour``)."""
    return {k: v for k, v in fields.items() if v is not None}


# --------------------------------------------------------------------- sync


class EmbedTokensResource:
    """Sync embed-token helper, returned by ``client.agents.embed_tokens(id)``."""

    def __init__(self, http: object, agent_id: str) -> None:
        self._http = http
        self._base = f"/v1/agents/{agent_id}/embed-tokens"

    def create(
        self,
        *,
        label: str | None = None,
        allowed_origins: list[str] | None = None,
        rate_limit_per_ip_per_hour: int | None = None,
        max_session_minutes: int | None = None,
    ) -> dict:
        """Mint a new embed token. The response includes ``plaintext``
        (the secret — save it!) and ``embed_snippet`` (paste-ready HTML).
        The server never returns the plaintext again."""
        return self._http.request(  # type: ignore[attr-defined]
            "POST", self._base,
            json=_create_body(
                label=label,
                allowed_origins=allowed_origins,
                rate_limit_per_ip_per_hour=rate_limit_per_ip_per_hour,
                max_session_minutes=max_session_minutes,
            ),
        )

    def list(self) -> list[dict]:
        """List existing tokens for this agent (metadata only — no plaintext)."""
        data = self._http.request("GET", self._base)  # type: ignore[attr-defined]
        return list(data.get("tokens") or [])

    def revoke(self, token_id: str) -> dict:
        """Revoke a token. Any live sessions using it are killed."""
        return self._http.request("DELETE", f"{self._base}/{token_id}")  # type: ignore[attr-defined]


# -------------------------------------------------------------------- async


class AsyncEmbedTokensResource:
    """Async sibling of :class:`EmbedTokensResource`."""

    def __init__(self, http: object, agent_id: str) -> None:
        self._http = http
        self._base = f"/v1/agents/{agent_id}/embed-tokens"

    async def create(
        self,
        *,
        label: str | None = None,
        allowed_origins: list[str] | None = None,
        rate_limit_per_ip_per_hour: int | None = None,
        max_session_minutes: int | None = None,
    ) -> dict:
        return await self._http.request(  # type: ignore[attr-defined]
            "POST", self._base,
            json=_create_body(
                label=label,
                allowed_origins=allowed_origins,
                rate_limit_per_ip_per_hour=rate_limit_per_ip_per_hour,
                max_session_minutes=max_session_minutes,
            ),
        )

    async def list(self) -> list[dict]:
        data = await self._http.request("GET", self._base)  # type: ignore[attr-defined]
        return list(data.get("tokens") or [])

    async def revoke(self, token_id: str) -> dict:
        return await self._http.request(  # type: ignore[attr-defined]
            "DELETE", f"{self._base}/{token_id}",
        )
