"""Text-to-speech endpoints — ``POST /v1/tts/generate``,
``POST /v1/tts/speak``, and streaming WS ``client.tts.stream(voice_id)``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..types import TtsResponse

if TYPE_CHECKING:
    from .._tts_stream import TtsStreamSession


def _ws_url_for(base_url: str, voice_id: int) -> str:
    """Compose the WS URL from the HTTP base, mirroring the helper in
    ``resources/agents.py``."""
    return (
        base_url.replace("http://", "ws://").replace("https://", "wss://")
        + f"/v1/voices/{voice_id}/stream"
    )

# Pricing constants (mirror developer-api/.env.example defaults). We
# expose these so callers can compute costs locally without rounding
# through a billing call. If the server changes pricing these stay in
# sync via SDK releases — read them at runtime, don't pin a version.
TTS_CREDITS_PER_REQUEST = 25
TTS_SPEAK_CREDITS_PER_REQUEST = 25  # saved/built-in voice → clone-sample price


@dataclass
class Estimate:
    """Result of a pre-flight cost estimate.

    ``credits`` is the number of credits the server will deduct on a
    successful call. ``chars`` is what we'd send as ``request_chars``
    in the request log."""

    credits: int
    chars: int
    endpoint: str


class _TtsBase:
    """Just the path constants shared between sync + async."""

    _generate_path = "/v1/tts/generate"
    _speak_path = "/v1/tts/speak"

    @staticmethod
    def estimate(
        *,
        text: str,
        voice: str | None = None,
        style_instruction: str | None = None,
    ) -> Estimate:
        """Compute the credit cost of a hypothetical TTS call without
        firing it. Pure local arithmetic — no HTTP round-trip.

        ``voice`` decides which pricing applies (``/v1/tts/speak`` uses
        the saved-voice / clone-sample tier, ``/v1/tts/generate`` uses
        the PromptTTS tier). The current server-side prices are flat
        per-request, so both tiers cost 25 credits today — that may
        diverge later, hence the branch."""
        chars = len(text) + (len(style_instruction) if style_instruction else 0)
        if voice:
            return Estimate(credits=TTS_SPEAK_CREDITS_PER_REQUEST, chars=chars, endpoint="/v1/tts/speak")
        return Estimate(credits=TTS_CREDITS_PER_REQUEST, chars=chars, endpoint="/v1/tts/generate")


class TtsResource(_TtsBase):
    def __init__(
        self,
        http: object,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._http = http
        # ``base_url`` + ``api_key`` are only used by :meth:`stream` —
        # kept optional so the historical ``TtsResource(http)`` call
        # site still works for REST-only callers.
        self._base_url = base_url or ""
        self._api_key = api_key or ""

    def stream(self, voice_id: int) -> TtsStreamSession:
        """Open a streaming-TTS WebSocket bound to a pre-registered voice.

        Returns an async context manager. Inside it, call :meth:`speak`
        and iterate to receive ``meta`` + binary ``audio`` + ``end``
        events. See :mod:`vocence._tts_stream` for the full event shape.

        ``voice_id`` is the integer id from
        :meth:`vocence.resources.voices.VoicesResource.list` (designed
        or cloned voice owned by the API key's user).
        """
        from .._tts_stream import TtsStreamSession

        return TtsStreamSession(
            url=_ws_url_for(self._base_url, voice_id),
            api_key=self._api_key,
        )

    def generate(
        self,
        *,
        text: str,
        style_instruction: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> TtsResponse:
        """PromptTTS — synthesize ``text`` in a voice described in prose.

        For a specific pre-defined speaker use :meth:`speak` instead.
        Up to 500 characters of text per call.

        ``timeout`` overrides the client-level default for THIS call only —
        useful for slow networks where 120s isn't enough."""
        body: dict[str, object] = {"text": text}
        if style_instruction is not None:
            body["style_instruction"] = style_instruction
        if model is not None:
            body["model"] = model
        data = self._http.request("POST", self._generate_path, json=body, timeout=timeout)  # type: ignore[attr-defined]
        return TtsResponse.model_validate(data)

    def speak(self, *, text: str, voice: str, timeout: float | None = None) -> TtsResponse:
        """Synthesize ``text`` in a pre-defined speaker's voice.

        Use :meth:`vocence.resources.voices.VoicesResource.builtin` to list
        the available speaker ids.
        """
        data = self._http.request(  # type: ignore[attr-defined]
            "POST",
            self._speak_path,
            json={"text": text, "voice": voice},
            timeout=timeout,
        )
        return TtsResponse.model_validate(data)


class AsyncTtsResource(_TtsBase):
    def __init__(
        self,
        http: object,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._http = http
        self._base_url = base_url or ""
        self._api_key = api_key or ""

    def stream(self, voice_id: int) -> TtsStreamSession:
        """Async-side identical to :meth:`TtsResource.stream`. Note
        that ``TtsStreamSession`` is the same class on both sides —
        it's natively async and the sync client wraps it the same
        way ``Vocence.agents.session`` does."""
        from .._tts_stream import TtsStreamSession

        return TtsStreamSession(
            url=_ws_url_for(self._base_url, voice_id),
            api_key=self._api_key,
        )

    async def generate(
        self,
        *,
        text: str,
        style_instruction: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> TtsResponse:
        body: dict[str, object] = {"text": text}
        if style_instruction is not None:
            body["style_instruction"] = style_instruction
        if model is not None:
            body["model"] = model
        data = await self._http.request("POST", self._generate_path, json=body, timeout=timeout)  # type: ignore[attr-defined]
        return TtsResponse.model_validate(data)

    async def speak(self, *, text: str, voice: str, timeout: float | None = None) -> TtsResponse:
        data = await self._http.request(  # type: ignore[attr-defined]
            "POST",
            self._speak_path,
            json={"text": text, "voice": voice},
            timeout=timeout,
        )
        return TtsResponse.model_validate(data)

    # Override the inherited sync ``estimate`` with an async wrapper so
    # ``AsyncVocence`` callers can ``await client.tts.estimate(...)``
    # symmetrically with the rest of the async surface. The body is
    # still pure-local arithmetic — no I/O — but typing it async
    # avoids the silent "I awaited a non-awaitable" TypeError users
    # otherwise hit when they uniformly await every method on the
    # async client.
    async def estimate(  # type: ignore[override]
        self,
        *,
        text: str,
        voice: str | None = None,
        style_instruction: str | None = None,
    ) -> Estimate:
        return _TtsBase.estimate(
            text=text, voice=voice, style_instruction=style_instruction
        )
