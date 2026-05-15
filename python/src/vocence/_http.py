"""Internal HTTP transport shared by sync + async clients.

Wraps ``httpx`` so the rest of the SDK only deals with parsed dicts and
typed errors. Everything that can fail (network, decoding, non-2xx
responses) is converted into a :class:`vocence.VocenceError` subclass.
"""

from __future__ import annotations

from typing import Any, BinaryIO

import httpx

from ._errors import APIConnectionError, VocenceError, error_for_status
from ._version import __version__

DEFAULT_BASE_URL = "https://api.vocence.ai"
DEFAULT_TIMEOUT = 120.0
USER_AGENT = f"vocence-python/{__version__}"


def _auth_header(api_key: str) -> dict[str, str]:
    # The API accepts either "Bearer voc_live_..." or the raw value;
    # always send the canonical Bearer form for clarity in server logs.
    raw = api_key.strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    return {"Authorization": f"Bearer {raw}"}


def _parse_body(resp: httpx.Response) -> Any:
    """Decode JSON if the upstream said so, else fall back to raw text."""
    ctype = (resp.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        try:
            return resp.json()
        except Exception:
            pass
    return resp.text


def _raise_for_status(resp: httpx.Response, body: Any) -> None:
    if resp.is_success:
        return
    detail: str | None = None
    if isinstance(body, dict):
        d = body.get("detail")
        if isinstance(d, str):
            detail = d
        elif d is not None:
            detail = str(d)
    elif isinstance(body, str) and body.strip():
        detail = body.strip()[:500]
    retry_after_hdr = resp.headers.get("retry-after")
    try:
        retry_after = float(retry_after_hdr) if retry_after_hdr else None
    except ValueError:
        retry_after = None
    raise error_for_status(
        resp.status_code,
        detail=detail,
        response=body if isinstance(body, dict) else None,
        retry_after=retry_after,
    )


# --------------------------------------------------------------------- sync


class SyncHttp:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, **_auth_header(api_key)},
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> SyncHttp:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        files: dict[str, tuple[str, BinaryIO | bytes, str]] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        try:
            resp = self._client.request(
                method,
                path,
                json=json,
                params=params,
                files=files,
                data=data,
            )
        except httpx.HTTPError as e:
            raise APIConnectionError(str(e)) from e
        body = _parse_body(resp)
        _raise_for_status(resp, body)
        return body if isinstance(body, dict) else {"data": body}


# --------------------------------------------------------------------- async


class AsyncHttp:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, **_auth_header(api_key)},
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncHttp:
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        files: dict[str, tuple[str, BinaryIO | bytes, str]] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        try:
            resp = await self._client.request(
                method,
                path,
                json=json,
                params=params,
                files=files,
                data=data,
            )
        except httpx.HTTPError as e:
            raise APIConnectionError(str(e)) from e
        body = _parse_body(resp)
        _raise_for_status(resp, body)
        return body if isinstance(body, dict) else {"data": body}


__all__ = ["SyncHttp", "AsyncHttp", "DEFAULT_BASE_URL", "VocenceError"]
