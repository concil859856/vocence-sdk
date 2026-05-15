"""Text-to-speech endpoints — ``POST /v1/tts/generate`` and
``POST /v1/tts/speak``."""

from __future__ import annotations

from ..types import TtsResponse


class _TtsBase:
    """Just the path constants shared between sync + async."""

    _generate_path = "/v1/tts/generate"
    _speak_path = "/v1/tts/speak"


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
