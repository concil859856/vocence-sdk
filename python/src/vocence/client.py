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
    AsyncFeedbackResource,
    AsyncSttResource,
    AsyncTtsResource,
    AsyncVoiceCloneResource,
    AsyncVoiceDesignResource,
    AsyncVoicesResource,
    FeedbackResource,
    SttResource,
    TtsResource,
    VoiceCloneResource,
    VoiceDesignResource,
    VoicesResource,
)

ENV_API_KEY = "VOCENCE_API_KEY"
ENV_BASE_URL = "VOCENCE_BASE_URL"


def _resolve_key(api_key: str | None) -> str:
    """Resolve an API key from (in order):

      1. The explicit ``api_key=`` argument.
      2. The ``VOCENCE_API_KEY`` env var.
      3. The CLI config file (``~/.vocence/config.json``) — same place
         ``vocence login`` writes to. If OS-keyring storage is enabled,
         the key is read from there instead.

    This third source means ``Vocence()`` from a Python REPL "just
    works" after the user has run ``vocence login`` — no env-var
    dance required.
    """
    if api_key and api_key.strip():
        return api_key.strip()
    env = os.environ.get(ENV_API_KEY)
    if env and env.strip():
        return env.strip()
    # Fall back to the CLI's persisted store. Lazy-imported because the
    # CLI subpackage pulls in Typer, which most Python integrators don't
    # care about — we don't want to penalise their import time.
    try:
        from .cli.config import get_api_key  # noqa: PLC0415 — intentional lazy import
        cli_key = get_api_key()
    except Exception:
        cli_key = None
    if cli_key:
        return cli_key
    raise ValueError(
        "API key is required. Pass `api_key=...`, set "
        f"{ENV_API_KEY} in the environment, or run `vocence login`."
    )


def _resolve_base_url(base_url: str | None) -> str:
    """Resolve the base URL from (in order):

      1. Explicit ``base_url=`` argument.
      2. ``VOCENCE_BASE_URL`` env var.
      3. CLI config (``vocence config set-base-url ...``).
      4. The default ``https://api.vocence.ai``.
    """
    if base_url and base_url.strip():
        return base_url.strip().rstrip("/")
    env = os.environ.get(ENV_BASE_URL)
    if env and env.strip():
        return env.strip().rstrip("/")
    try:
        from .cli.config import get_base_url  # noqa: PLC0415
        cli_url = get_base_url()
    except Exception:
        cli_url = None
    return (cli_url or DEFAULT_BASE_URL).rstrip("/")


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
        max_retries: int = 2,
        retry_mutations_on_5xx: bool = False,
    ) -> None:
        """Construct a sync client.

        ``max_retries`` (default 2) controls auto-retry on 429 +
        transient 5xx / network errors. Set to ``0`` to disable.

        ``retry_mutations_on_5xx`` defaults to ``False`` — POST/PATCH/DELETE
        are NOT retried on 5xx by default (could double-charge / double-create).
        GET + 429 are always retried up to ``max_retries`` attempts.
        """
        key = _resolve_key(api_key)
        self._base_url = _resolve_base_url(base_url)
        self._http = SyncHttp(
            key,
            base_url=self._base_url,
            timeout=timeout,
            http_client=http_client,
            max_retries=max_retries,
            retry_mutations_on_5xx=retry_mutations_on_5xx,
        )

        self.tts = TtsResource(self._http)
        self.stt = SttResource(self._http)
        self.voice_clone = VoiceCloneResource(self._http)
        self.voice_design = VoiceDesignResource(self._http)
        self.voices = VoicesResource(self._http)
        self.agent_tools = AgentToolsResource(self._http)
        self.agents = AgentsResource(self._http, base_url=self._base_url, api_key=key)
        self.account = AccountResource(self._http)
        self.feedback = FeedbackResource(self._http)

    @property
    def last_request_id(self) -> str | None:
        """Server-issued request id from the most recent HTTP call.
        Useful for support tickets — paste this when reporting a bug."""
        return self._http.last_request_id

    def health(self, *, timeout: float = 10.0) -> bool:
        """Round-trip a tiny authenticated call; returns ``True`` iff the
        API host is reachable AND the configured key is valid.

        Use this before starting a long batch — it fails fast on a bad
        key or an unreachable host. Charges nothing (``GET /v1/account``)."""
        from ._errors import VocenceError
        try:
            self._http.request("GET", "/v1/account")
            return True
        except VocenceError:
            return False

    def __repr__(self) -> str:
        # Mask the key so the SDK can't leak secrets through stack
        # traces, debug logs, or accidental ``print(client)`` calls.
        from ._http import redact_key
        return f"Vocence(base_url={self._base_url!r}, api_key={redact_key(self._http._api_key)!r})"

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
        max_retries: int = 2,
        retry_mutations_on_5xx: bool = False,
    ) -> None:
        """Async counterpart of :class:`Vocence`. Same retry semantics."""
        key = _resolve_key(api_key)
        self._api_key = key
        self._base_url = _resolve_base_url(base_url)
        self._http = AsyncHttp(
            key,
            base_url=self._base_url,
            timeout=timeout,
            http_client=http_client,
            max_retries=max_retries,
            retry_mutations_on_5xx=retry_mutations_on_5xx,
        )

        self.tts = AsyncTtsResource(self._http)
        self.stt = AsyncSttResource(self._http)
        self.voice_clone = AsyncVoiceCloneResource(self._http)
        self.voice_design = AsyncVoiceDesignResource(self._http)
        self.voices = AsyncVoicesResource(self._http)
        self.agent_tools = AsyncAgentToolsResource(self._http)
        self.agents = AsyncAgentsResource(self._http, base_url=self._base_url, api_key=key)
        self.account = AsyncAccountResource(self._http)
        self.feedback = AsyncFeedbackResource(self._http)

    @property
    def last_request_id(self) -> str | None:
        return self._http.last_request_id

    async def health(self, *, timeout: float = 10.0) -> bool:
        """Async counterpart of :meth:`Vocence.health`."""
        from ._errors import VocenceError
        try:
            await self._http.request("GET", "/v1/account")
            return True
        except VocenceError:
            return False

    def __repr__(self) -> str:
        from ._http import redact_key
        return f"AsyncVocence(base_url={self._base_url!r}, api_key={redact_key(self._api_key)!r})"

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncVocence:
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.aclose()
