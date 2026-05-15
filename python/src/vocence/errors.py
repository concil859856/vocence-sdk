"""Public re-export of the SDK's exception hierarchy.

Users typically write ``from vocence import errors`` and then refer to
``errors.AuthenticationError``, ``errors.RateLimitError``, etc.
"""

from ._errors import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    InsufficientCreditsError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UpstreamError,
    VocenceError,
)

__all__ = [
    "APIConnectionError",
    "AuthenticationError",
    "BadRequestError",
    "InsufficientCreditsError",
    "NotFoundError",
    "PermissionDeniedError",
    "RateLimitError",
    "UpstreamError",
    "VocenceError",
]
