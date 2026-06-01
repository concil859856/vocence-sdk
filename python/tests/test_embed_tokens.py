"""Embed-token resource — create / list / revoke."""

from __future__ import annotations

import httpx
import pytest
import respx

from vocence import AsyncVocence, Vocence

from .conftest import API_KEY, BASE_URL


def test_create_drops_unset_fields() -> None:
    """If the caller passes nothing the body should be ``{}`` so the
    server's defaults apply for every field. Passing ``None``
    explicitly should NOT serialize as ``null``."""
    client = Vocence(api_key=API_KEY, base_url=BASE_URL)
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as r:
        route = r.post("/v1/agents/ag_x/embed-tokens").mock(
            return_value=httpx.Response(
                201, json={"plaintext": "vet_secret", "token": {"id": "t1"}, "embed_snippet": "<script>"},
            ),
        )
        out = client.agents.embed_tokens("ag_x").create()
        assert out["plaintext"] == "vet_secret"
        body = route.calls.last.request.content.decode()
        # No keys with null values.
        assert "null" not in body


def test_create_passes_through_explicit_fields() -> None:
    client = Vocence(api_key=API_KEY, base_url=BASE_URL)
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as r:
        route = r.post("/v1/agents/ag_x/embed-tokens").mock(
            return_value=httpx.Response(201, json={"plaintext": "vet_secret"}),
        )
        client.agents.embed_tokens("ag_x").create(
            label="staging",
            allowed_origins=["https://staging.example.com"],
            rate_limit_per_ip_per_hour=60,
            max_session_minutes=10,
        )
        body = route.calls.last.request.content.decode()
        assert '"label":"staging"' in body
        assert '"rate_limit_per_ip_per_hour":60' in body
        assert "staging.example.com" in body


def test_list_unwraps_tokens() -> None:
    """Mirror the dashboard's wrapped reply ``{tokens: [...]}``."""
    client = Vocence(api_key=API_KEY, base_url=BASE_URL)
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as r:
        r.get("/v1/agents/ag_x/embed-tokens").mock(
            return_value=httpx.Response(200, json={"tokens": [{"id": "t1", "label": "demo"}]}),
        )
        out = client.agents.embed_tokens("ag_x").list()
        assert out == [{"id": "t1", "label": "demo"}]


def test_revoke_hits_delete() -> None:
    client = Vocence(api_key=API_KEY, base_url=BASE_URL)
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as r:
        r.delete("/v1/agents/ag_x/embed-tokens/t1").mock(
            return_value=httpx.Response(200, json={"ok": True}),
        )
        out = client.agents.embed_tokens("ag_x").revoke("t1")
        assert out == {"ok": True}


@pytest.mark.asyncio
async def test_async_embed_tokens_parity() -> None:
    aclient = AsyncVocence(api_key=API_KEY, base_url=BASE_URL)
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as r:
        r.post("/v1/agents/ag_y/embed-tokens").mock(
            return_value=httpx.Response(201, json={"plaintext": "vet_secret"}),
        )
        r.get("/v1/agents/ag_y/embed-tokens").mock(
            return_value=httpx.Response(200, json={"tokens": []}),
        )
        et = aclient.agents.embed_tokens("ag_y")
        assert (await et.create())["plaintext"] == "vet_secret"
        assert await et.list() == []
    await aclient.aclose()
