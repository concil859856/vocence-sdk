"""Text-to-speech endpoints — ``POST /v1/tts/generate`` and
``POST /v1/tts/speak``."""

from __future__ import annotations

from dataclasses import dataclass

from ..types import TtsResponse


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
    def __init__(self, http: object) -> None:
        self._http = http

    def generate(
        self,
        *,
        text: str,
        style_instruction: str | None = None,
        model: str | None = None,
    ) -> TtsResponse:
        """PromptTTS — synthesize ``text`` in a voice described in prose.

        For a specific pre-defined speaker use :meth:`speak` instead.
        Up to 500 characters of text per call.
        """
        body: dict[str, object] = {"text": text}
        if style_instruction is not None:
            body["style_instruction"] = style_instruction
        if model is not None:
            body["model"] = model
        data = self._http.request("POST", self._generate_path, json=body)  # type: ignore[attr-defined]
        return TtsResponse.model_validate(data)

    def speak(self, *, text: str, voice: str) -> TtsResponse:
        """Synthesize ``text`` in a pre-defined speaker's voice.

        Use :meth:`vocence.resources.voices.VoicesResource.builtin` to list
        the available speaker ids.
        """
        data = self._http.request(  # type: ignore[attr-defined]
            "POST",
            self._speak_path,
            json={"text": text, "voice": voice},
        )
        return TtsResponse.model_validate(data)


class AsyncTtsResource(_TtsBase):
    def __init__(self, http: object) -> None:
        self._http = http

    async def generate(
        self,
        *,
        text: str,
        style_instruction: str | None = None,
        model: str | None = None,
    ) -> TtsResponse:
        body: dict[str, object] = {"text": text}
        if style_instruction is not None:
            body["style_instruction"] = style_instruction
        if model is not None:
            body["model"] = model
        data = await self._http.request("POST", self._generate_path, json=body)  # type: ignore[attr-defined]
        return TtsResponse.model_validate(data)

    async def speak(self, *, text: str, voice: str) -> TtsResponse:
        data = await self._http.request(  # type: ignore[attr-defined]
            "POST",
            self._speak_path,
            json={"text": text, "voice": voice},
        )
        return TtsResponse.model_validate(data)
