"""Top-level Vocence + AsyncVocence client classes."""

from __future__ import annotations

import os
from typing import Any

import httpx

from ._http import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, AsyncHttp, SyncHttp
from .resources import (
    AccountResource,
    AgentsResource,
    AgentToolsResource,
    AsyncAccountResource,
    AsyncAgentsResource,
    AsyncAgentToolsResource,
    AsyncSttResource,
    AsyncTtsResource,
    AsyncVoiceCloneResource,
    AsyncVoiceDesignResource,
    AsyncVoicesResource,
    SttResource,
    TtsResource,
    VoiceCloneResource,
    VoiceDesignResource,
    VoicesResource,
)

ENV_API_KEY = "VOCENCE_API_KEY"
ENV_BASE_URL = "VOCENCE_BASE_URL"


def _resolve_key(api_key: str | None) -> str:
    key = (api_key or os.environ.get(ENV_API_KEY) or "").strip()
    if not key:
        raise ValueError(
            "API key is required. Pass `api_key=...` or set the "
            f"{ENV_API_KEY} environment variable."
        )
    return key


def _resolve_base_url(base_url: str | None) -> str:
    return (base_url or os.environ.get(ENV_BASE_URL) or DEFAULT_BASE_URL).rstrip("/")


class Vocence:
    """Synchronous client.

    Examples
    --------
    >>> client = Vocence(api_key="voc_live_...")
    >>> audio = client.tts.speak(text="Hello", voice="design-aria")
    >>> print(audio.audio_url)
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.Client | None = None,
    ) -> None:
        key = _resolve_key(api_key)
        self._base_url = _resolve_base_url(base_url)
        self._http = SyncHttp(key, base_url=self._base_url, timeout=timeout, http_client=http_client)

        self.tts = TtsResource(self._http)
        self.stt = SttResource(self._http)
        self.voice_clone = VoiceCloneResource(self._http)
        self.voice_design = VoiceDesignResource(self._http)
        self.voices = VoicesResource(self._http)
        self.agent_tools = AgentToolsResource(self._http)
        self.agents = AgentsResource(self._http, base_url=self._base_url, api_key=key)
        self.account = AccountResource(self._http)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Vocence:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


class AsyncVocence:
    """Asynchronous client.

    Mirrors :class:`Vocence` exactly — every method is the awaitable
    counterpart of its sync sibling.

    Examples
    --------
    >>> async with AsyncVocence(api_key="voc_live_...") as client:
    ...     audio = await client.tts.speak(text="Hello", voice="design-aria")
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        key = _resolve_key(api_key)
        self._api_key = key
        self._base_url = _resolve_base_url(base_url)
        self._http = AsyncHttp(key, base_url=self._base_url, timeout=timeout, http_client=http_client)

        self.tts = AsyncTtsResource(self._http)
        self.stt = AsyncSttResource(self._http)
        self.voice_clone = AsyncVoiceCloneResource(self._http)
        self.voice_design = AsyncVoiceDesignResource(self._http)
        self.voices = AsyncVoicesResource(self._http)
        self.agent_tools = AsyncAgentToolsResource(self._http)
        self.agents = AsyncAgentsResource(self._http, base_url=self._base_url, api_key=key)
        self.account = AsyncAccountResource(self._http)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncVocence:
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.aclose()
