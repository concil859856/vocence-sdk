"""Vocence Developer API — Python SDK.

>>> from vocence import Vocence
>>> client = Vocence(api_key="voc_live_...")
>>> audio = client.tts.speak(text="Hello", voice="design-aria")
>>> print(audio.audio_url)

See https://vocence.ai/docs/api for the full endpoint reference and
https://github.com/concil859856/vocence-sdk for the source repo.
"""

from __future__ import annotations

from . import errors
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
from ._streaming import AgentEvent, AgentSession, AudioFrame
from ._streaming_sync import SyncAgentSession
from ._version import __version__
from .client import AsyncVocence, Vocence

__all__ = [
    "APIConnectionError",
    "AgentEvent",
    "AgentSession",
    "AsyncVocence",
    "AudioFrame",
    "AuthenticationError",
    "BadRequestError",
    "InsufficientCreditsError",
    "NotFoundError",
    "PermissionDeniedError",
    "RateLimitError",
    "SyncAgentSession",
    "UpstreamError",
    "Vocence",
    "VocenceError",
    "__version__",
    "errors",
]
