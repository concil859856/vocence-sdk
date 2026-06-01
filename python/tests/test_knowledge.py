"""Knowledge-ingest resource — covers the proxy URL shape, body
serialization (None drop), PDF multipart upload, and the async/sync
parity that the rest of the SDK enforces."""

from __future__ import annotations

import io

import httpx
import pytest
import respx

from vocence import AsyncVocence, Vocence

from .conftest import API_KEY, BASE_URL


# --------------------------------------------------------------------- sync


def test_knowledge_ingest_text_drops_none_title() -> None:
    """``title=None`` must NOT serialize so the server applies its
    own default; otherwise we'd be sending a bogus null label."""
    client = Vocence(api_key=API_KEY, base_url=BASE_URL)
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as r:
        route = r.post("/v1/agents/ag_123/knowledge/ingest/text").mock(
            return_value=httpx.Response(200, json={"job_id": "j1"}),
        )
        out = client.agents.knowledge("ag_123").ingest_text("hello world")
        assert out == {"job_id": "j1"}
        body = route.calls.last.request.content.decode()
        # Title omitted because we passed None — only ``content`` survives.
        assert '"content":"hello world"' in body
        assert '"title"' not in body


def test_knowledge_ingest_url_passes_max_depth() -> None:
    client = Vocence(api_key=API_KEY, base_url=BASE_URL)
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as r:
        route = r.post("/v1/agents/ag_123/knowledge/ingest/url").mock(
            return_value=httpx.Response(200, json={"job_id": "j2"}),
        )
        client.agents.knowledge("ag_123").ingest_url(
            "https://example.com/docs", max_depth=1,
        )
        body = route.calls.last.request.content.decode()
        assert '"url":"https://example.com/docs"' in body
        assert '"max_depth":1' in body


def test_knowledge_ingest_sitemap_includes_filters() -> None:
    client = Vocence(api_key=API_KEY, base_url=BASE_URL)
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as r:
        route = r.post("/v1/agents/ag_123/knowledge/ingest/sitemap").mock(
            return_value=httpx.Response(200, json={"job_id": "j3"}),
        )
        client.agents.knowledge("ag_123").ingest_sitemap(
            "https://example.com/sitemap.xml",
            include=[r"^https://example\.com/docs/"],
            max_pages=100,
        )
        body = route.calls.last.request.content.decode()
        assert '"max_pages":100' in body
        assert "docs" in body  # the regex made it into the body


def test_knowledge_ingest_pdf_uploads_multipart() -> None:
    """Path / bytes / file-like inputs all resolve to a multipart form
    field named ``file`` with the correct content-type."""
    client = Vocence(api_key=API_KEY, base_url=BASE_URL)
    fake_pdf = b"%PDF-1.4\n%fake\n%%EOF"
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as r:
        route = r.post("/v1/agents/ag_123/knowledge/ingest/pdf").mock(
            return_value=httpx.Response(200, json={"job_id": "j4"}),
        )
        client.agents.knowledge("ag_123").ingest_pdf(
            io.BytesIO(fake_pdf), title="My doc",
        )
        req = route.calls.last.request
        ct = req.headers.get("content-type", "")
        assert ct.startswith("multipart/form-data"), ct
        # The body has the file content + the title form field.
        raw = req.content
        assert fake_pdf in raw
        assert b"My doc" in raw


def test_knowledge_list_sources_unwraps() -> None:
    """The proxy wraps the dashboard reply in ``{sources: [...]}``; the
    SDK should return the inner list (matches every other ``list()``
    method on this client)."""
    client = Vocence(api_key=API_KEY, base_url=BASE_URL)
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as r:
        r.get("/v1/agents/ag_123/knowledge/sources").mock(
            return_value=httpx.Response(200, json={"sources": [{"id": "s1"}]}),
        )
        out = client.agents.knowledge("ag_123").sources()
        assert out == [{"id": "s1"}]


def test_knowledge_job_passthrough() -> None:
    client = Vocence(api_key=API_KEY, base_url=BASE_URL)
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as r:
        r.get("/v1/agents/ag_123/knowledge/jobs/j99").mock(
            return_value=httpx.Response(200, json={"status": "done", "progress": 1.0}),
        )
        out = client.agents.knowledge("ag_123").job("j99")
        assert out["status"] == "done"


# -------------------------------------------------------------------- async


@pytest.mark.asyncio
async def test_async_knowledge_parity() -> None:
    """Smoke check that the async resource hits the same URL shapes as
    the sync one — keeps the two from drifting silently."""
    aclient = AsyncVocence(api_key=API_KEY, base_url=BASE_URL)
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as r:
        r.post("/v1/agents/ag_a/knowledge/ingest/text").mock(
            return_value=httpx.Response(200, json={"job_id": "ja"}),
        )
        r.get("/v1/agents/ag_a/knowledge/sources").mock(
            return_value=httpx.Response(200, json={"sources": []}),
        )
        kn = aclient.agents.knowledge("ag_a")
        assert await kn.ingest_text("x") == {"job_id": "ja"}
        assert await kn.sources() == []
    await aclient.aclose()
