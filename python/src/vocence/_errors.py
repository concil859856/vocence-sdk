"""Public exception hierarchy.

Every error the SDK raises is a subclass of :class:`VocenceError`, so callers
can ``except VocenceError`` to catch anything that originated from us.
Specific subclasses let callers handle individual failure modes (e.g. retry
on rate-limit, top-up on insufficient credits) without parsing strings.
"""

from __future__ import annotations

from typing import Any


class VocenceError(Exception):
    """Base class for every error raised by the SDK.

    Attributes
    ----------
    status_code:
        HTTP status code from the upstream response, if the error originated
        from an HTTP call. ``None`` for client-side validation errors that
        never made it to the wire.
    detail:
        The ``detail`` field from the upstream JSON error body, when present.
    response:
        The parsed JSON body of the upstream response, when available.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: str | None = None,
        response: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail
        self.response = response


class AuthenticationError(VocenceError):
    """HTTP 401 — the API key was missing, malformed, or unknown."""


class PermissionDeniedError(VocenceError):
    """HTTP 403 — the key is valid but lacks permission (e.g. revoked)."""


class NotFoundError(VocenceError):
    """HTTP 404 — the resource (voice id, agent id, tool id, …) does not exist."""


class BadRequestError(VocenceError):
    """HTTP 400 / 422 — the request was malformed."""


class InsufficientCreditsError(VocenceError):
    """HTTP 402 — not enough credits, or the account lacks a Premium plan."""


class RateLimitError(VocenceError):
    """HTTP 429 — too many requests.

    ``retry_after`` carries the number of seconds the server asked us to wait
    (from the ``Retry-After`` header) when present.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class UpstreamError(VocenceError):
    """HTTP 502 / 503 / 504 — an upstream provider failed (TTS chute, STT
    server, voice-clone inference). The caller can usually retry."""


class APIConnectionError(VocenceError):
    """Network-level failure — DNS, TLS, connection refused, etc."""


_STATUS_MAP: dict[int, type[VocenceError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    402: InsufficientCreditsError,
    403: PermissionDeniedError,
    404: NotFoundError,
    422: BadRequestError,
    429: RateLimitError,
    500: UpstreamError,
    502: UpstreamError,
    503: UpstreamError,
    504: UpstreamError,
}


def error_for_status(
    status: int,
    *,
    detail: str | None,
    response: Any | None,
    retry_after: float | None = None,
) -> VocenceError:
    """Map an HTTP status code to the most specific SDK exception subclass."""
    cls = _STATUS_MAP.get(status, VocenceError)
    msg = detail or f"HTTP {status}"
    if cls is RateLimitError:
        return RateLimitError(msg, status_code=status, detail=detail, response=response, retry_after=retry_after)
    return cls(msg, status_code=status, detail=detail, response=response)
