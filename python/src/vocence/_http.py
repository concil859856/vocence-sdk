"""Internal HTTP transport shared by sync + async clients.

Wraps ``httpx`` so the rest of the SDK only deals with parsed dicts and
typed errors. Everything that can fail (network, decoding, non-2xx
responses) is converted into a :class:`vocence.VocenceError` subclass.

Retry behavior
--------------
GET requests + any request that returns 429 retry with exponential
backoff + jitter. Other 4xx (auth, bad request) are NOT retried — those
won't change. Mutating verbs (POST/PATCH/DELETE) are NOT retried by
default on 5xx because re-sending could double-charge / double-create;
callers can opt in via :class:`Vocence` constructor flags.

We respect ``Retry-After`` on 429 responses; otherwise sleep grows as
``base * 2**attempt`` with ±25% jitter, capped at ``max_wait``.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Iterable
from typing import Any, BinaryIO

import httpx

from ._errors import (
    APIConnectionError,
    RateLimitError,
    UpstreamError,
    VocenceError,
    error_for_status,
)
from ._version import __version__

DEFAULT_BASE_URL = "https://api.vocence.ai"
DEFAULT_TIMEOUT = 120.0
USER_AGENT = f"vocence-python/{__version__}"

# 5xx codes that are typically transient — TTS provider hiccup, upstream
# voice-clone server briefly down, dashboard restart. Worth retrying.
_TRANSIENT_5XX: frozenset[int] = frozenset({502, 503, 504})


def _auth_header(api_key: str) -> dict[str, str]:
    # The API accepts either "Bearer voc_live_..." or the raw value;
    # always send the canonical Bearer form for clarity in server logs.
    raw = api_key.strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    return {"Authorization": f"Bearer {raw}"}


def redact_key(value: str | None) -> str:
    """Render an API key in ``voc_live_XXXX…XXXX`` form for safe display.

    Use anywhere the SDK might print, log, or otherwise expose a key —
    error messages, debug hooks, masked CLI output. Always shorten to a
    fixed shape regardless of input length so the actual entropy never
    appears in process listings, log files, or screenshots."""
    if not value:
        return "(unset)"
    s = value.strip()
    if s.lower().startswith("bearer "):
        s = s[7:].strip()
    if len(s) <= 12:
        return "*" * len(s)
    return f"{s[:12]}…{s[-4:]}"


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


def _should_retry(method: str, exc: VocenceError, *, retry_mutations_on_5xx: bool) -> bool:
    """Decide whether the failed request can safely be retried."""
    if isinstance(exc, RateLimitError):
        return True  # always retry rate limits, regardless of verb
    if isinstance(exc, APIConnectionError):
        return method == "GET" or retry_mutations_on_5xx
    if isinstance(exc, UpstreamError) and exc.status_code in _TRANSIENT_5XX:
        return method == "GET" or retry_mutations_on_5xx
    return False


def _backoff_sleep(attempt: int, *, base: float, max_wait: float, hint: float | None) -> float:
    """Compute the sleep duration for ``attempt`` (0-indexed retry number).
    Honors ``hint`` (Retry-After) when present, else exponential backoff
    with ±25% jitter, capped at ``max_wait``."""
    if hint is not None and hint >= 0:
        return min(hint, max_wait)
    raw = base * (2 ** attempt)
    jitter = raw * 0.25 * (random.random() * 2 - 1)
    return max(0.0, min(raw + jitter, max_wait))


# --------------------------------------------------------------------- sync


class SyncHttp:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.Client | None = None,
        max_retries: int = 2,
        retry_base_seconds: float = 0.5,
        retry_max_seconds: float = 8.0,
        retry_mutations_on_5xx: bool = False,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, **_auth_header(api_key)},
        )
        self._max_retries = max(0, int(max_retries))
        self._retry_base = retry_base_seconds
        self._retry_max = retry_max_seconds
        self._retry_mutations = bool(retry_mutations_on_5xx)
        self.last_request_id: str | None = None

    def __repr__(self) -> str:
        return f"SyncHttp(base_url={self._base_url!r}, api_key={redact_key(self._api_key)!r})"

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
        timeout: float | None = None,
    ) -> Any:
        last_exc: VocenceError | None = None
        # Per-call timeout override — httpx accepts a float for the
        # whole-request budget.
        kw: dict[str, Any] = {"json": json, "params": params, "files": files, "data": data}
        if timeout is not None:
            kw["timeout"] = timeout
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.request(method, path, **kw)
            except httpx.HTTPError as e:
                last_exc = APIConnectionError(str(e))
            else:
                body = _parse_body(resp)
                # Capture request_id from body or X-Request-ID header.
                self.last_request_id = _extract_request_id(resp, body)
                try:
                    _raise_for_status(resp, body)
                except VocenceError as e:
                    last_exc = e
                else:
                    return body if isinstance(body, dict) else {"data": body}
            # Decide whether to retry.
            assert last_exc is not None
            if attempt >= self._max_retries:
                raise last_exc
            if not _should_retry(method.upper(), last_exc, retry_mutations_on_5xx=self._retry_mutations):
                raise last_exc
            hint = getattr(last_exc, "retry_after", None)
            time.sleep(_backoff_sleep(attempt, base=self._retry_base, max_wait=self._retry_max, hint=hint))
        raise last_exc  # unreachable but keeps the type-checker happy


# --------------------------------------------------------------------- async


class AsyncHttp:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
        max_retries: int = 2,
        retry_base_seconds: float = 0.5,
        retry_max_seconds: float = 8.0,
        retry_mutations_on_5xx: bool = False,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, **_auth_header(api_key)},
        )
        self._max_retries = max(0, int(max_retries))
        self._retry_base = retry_base_seconds
        self._retry_max = retry_max_seconds
        self._retry_mutations = bool(retry_mutations_on_5xx)
        self.last_request_id: str | None = None

    def __repr__(self) -> str:
        return f"AsyncHttp(base_url={self._base_url!r}, api_key={redact_key(self._api_key)!r})"

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
        timeout: float | None = None,
    ) -> Any:
        last_exc: VocenceError | None = None
        kw: dict[str, Any] = {"json": json, "params": params, "files": files, "data": data}
        if timeout is not None:
            kw["timeout"] = timeout
        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._client.request(method, path, **kw)
            except httpx.HTTPError as e:
                last_exc = APIConnectionError(str(e))
            else:
                body = _parse_body(resp)
                self.last_request_id = _extract_request_id(resp, body)
                try:
                    _raise_for_status(resp, body)
                except VocenceError as e:
                    last_exc = e
                else:
                    return body if isinstance(body, dict) else {"data": body}
            assert last_exc is not None
            if attempt >= self._max_retries:
                raise last_exc
            if not _should_retry(method.upper(), last_exc, retry_mutations_on_5xx=self._retry_mutations):
                raise last_exc
            hint = getattr(last_exc, "retry_after", None)
            await asyncio.sleep(_backoff_sleep(attempt, base=self._retry_base, max_wait=self._retry_max, hint=hint))
        raise last_exc


# --------------------------------------------------------------------- helpers


def _extract_request_id(resp: httpx.Response, body: Any) -> str | None:
    """Prefer the server-issued ``request_id`` from the JSON body; fall
    back to the ``X-Request-ID`` response header."""
    if isinstance(body, dict):
        rid = body.get("request_id")
        if isinstance(rid, str) and rid:
            return rid
    hdr = resp.headers.get("x-request-id")
    return hdr if hdr else None


__all__: Iterable[str] = ["SyncHttp", "AsyncHttp", "DEFAULT_BASE_URL", "VocenceError"]
