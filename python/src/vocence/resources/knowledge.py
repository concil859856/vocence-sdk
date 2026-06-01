"""Per-agent knowledge ingestion — mirrors
``/v1/agents/{agent_id}/knowledge/*`` on the developer API.

Accessed via ``client.agents.knowledge(agent_id)``::

    kn = client.agents.knowledge("ag_123")
    job = kn.ingest_url("https://docs.example.com")
    while True:
        status = kn.job(job["job_id"])
        if status["status"] in ("done", "failed"):
            break
        time.sleep(2)

Supports text, markdown, single URL, sitemap crawl, and PDF upload
(≤ 50 MB). Each ingest call returns immediately with a ``job_id``;
poll :meth:`job` until ``status`` is ``done`` or ``failed``.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any, Union


# A PDF upload can be either a filesystem path or an already-opened
# file-like object. The async / sync resources resolve both into raw
# bytes before they reach the HTTP layer.
PdfInput = Union[str, Path, bytes, IO[bytes]]


def _read_pdf(source: PdfInput) -> tuple[bytes, str]:
    """Resolve a PdfInput into (raw_bytes, filename)."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        return path.read_bytes(), path.name
    if isinstance(source, (bytes, bytearray)):
        return bytes(source), "document.pdf"
    # File-like object.
    data = source.read()
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("file-like .read() returned non-bytes data")
    name = getattr(source, "name", None) or "document.pdf"
    return bytes(data), Path(str(name)).name


def _ingest_body(**fields: Any) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


# --------------------------------------------------------------------- sync


class KnowledgeResource:
    """Sync knowledge helper, returned by ``client.agents.knowledge(agent_id)``."""

    def __init__(self, http: object, agent_id: str) -> None:
        self._http = http
        self._base = f"/v1/agents/{agent_id}/knowledge"

    # ----- reads -----------------------------------------------------

    def sources(self) -> list[dict]:
        """List ingested knowledge sources for the agent."""
        data = self._http.request("GET", f"{self._base}/sources")  # type: ignore[attr-defined]
        return list(data.get("sources") or [])

    def delete_source(self, source_id: str) -> dict:
        """Remove a previously ingested source."""
        return self._http.request("DELETE", f"{self._base}/sources/{source_id}")  # type: ignore[attr-defined]

    def job(self, job_id: str) -> dict:
        """Poll an in-progress ingest job. Returns ``{status, progress, ...}``."""
        return self._http.request("GET", f"{self._base}/jobs/{job_id}")  # type: ignore[attr-defined]

    # ----- ingests ---------------------------------------------------

    def ingest_text(self, content: str, *, title: str | None = None) -> dict:
        return self._http.request(  # type: ignore[attr-defined]
            "POST", f"{self._base}/ingest/text",
            json=_ingest_body(content=content, title=title),
        )

    def ingest_markdown(self, content: str, *, title: str | None = None) -> dict:
        return self._http.request(  # type: ignore[attr-defined]
            "POST", f"{self._base}/ingest/markdown",
            json=_ingest_body(content=content, title=title),
        )

    def ingest_url(
        self,
        url: str,
        *,
        title: str | None = None,
        max_depth: int = 0,
    ) -> dict:
        """Ingest a single page (max_depth=0) or page + one hop of internal links (max_depth=1)."""
        return self._http.request(  # type: ignore[attr-defined]
            "POST", f"{self._base}/ingest/url",
            json=_ingest_body(url=url, title=title, max_depth=max_depth),
        )

    def ingest_sitemap(
        self,
        url: str,
        *,
        title: str | None = None,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        max_pages: int = 500,
    ) -> dict:
        """Crawl a sitemap.xml and ingest every page (capped at ``max_pages``,
        with optional include/exclude regex filters applied to each URL)."""
        return self._http.request(  # type: ignore[attr-defined]
            "POST", f"{self._base}/ingest/sitemap",
            json=_ingest_body(
                url=url, title=title,
                include=include, exclude=exclude,
                max_pages=max_pages,
            ),
        )

    def ingest_pdf(self, source: PdfInput, *, title: str | None = None) -> dict:
        """Upload a PDF (≤ 50 MB) for OCR + parse + ingest. ``source`` can be
        a path-like, raw bytes, or a binary file-like."""
        content, filename = _read_pdf(source)
        files = {"file": (filename, content, "application/pdf")}
        form: dict[str, Any] = {}
        if title:
            form["title"] = title
        return self._http.request(  # type: ignore[attr-defined]
            "POST", f"{self._base}/ingest/pdf",
            files=files, data=form or None,
        )


# -------------------------------------------------------------------- async


class AsyncKnowledgeResource:
    """Async sibling of :class:`KnowledgeResource`."""

    def __init__(self, http: object, agent_id: str) -> None:
        self._http = http
        self._base = f"/v1/agents/{agent_id}/knowledge"

    async def sources(self) -> list[dict]:
        data = await self._http.request("GET", f"{self._base}/sources")  # type: ignore[attr-defined]
        return list(data.get("sources") or [])

    async def delete_source(self, source_id: str) -> dict:
        return await self._http.request(  # type: ignore[attr-defined]
            "DELETE", f"{self._base}/sources/{source_id}",
        )

    async def job(self, job_id: str) -> dict:
        return await self._http.request(  # type: ignore[attr-defined]
            "GET", f"{self._base}/jobs/{job_id}",
        )

    async def ingest_text(self, content: str, *, title: str | None = None) -> dict:
        return await self._http.request(  # type: ignore[attr-defined]
            "POST", f"{self._base}/ingest/text",
            json=_ingest_body(content=content, title=title),
        )

    async def ingest_markdown(self, content: str, *, title: str | None = None) -> dict:
        return await self._http.request(  # type: ignore[attr-defined]
            "POST", f"{self._base}/ingest/markdown",
            json=_ingest_body(content=content, title=title),
        )

    async def ingest_url(
        self,
        url: str,
        *,
        title: str | None = None,
        max_depth: int = 0,
    ) -> dict:
        return await self._http.request(  # type: ignore[attr-defined]
            "POST", f"{self._base}/ingest/url",
            json=_ingest_body(url=url, title=title, max_depth=max_depth),
        )

    async def ingest_sitemap(
        self,
        url: str,
        *,
        title: str | None = None,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        max_pages: int = 500,
    ) -> dict:
        return await self._http.request(  # type: ignore[attr-defined]
            "POST", f"{self._base}/ingest/sitemap",
            json=_ingest_body(
                url=url, title=title,
                include=include, exclude=exclude,
                max_pages=max_pages,
            ),
        )

    async def ingest_pdf(self, source: PdfInput, *, title: str | None = None) -> dict:
        content, filename = _read_pdf(source)
        files = {"file": (filename, content, "application/pdf")}
        form: dict[str, Any] = {}
        if title:
            form["title"] = title
        return await self._http.request(  # type: ignore[attr-defined]
            "POST", f"{self._base}/ingest/pdf",
            files=files, data=form or None,
        )
