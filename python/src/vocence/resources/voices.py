"""Voice catalog endpoints — built-in speakers, saved voices, and the
``speak`` shortcut for saved voices."""

from __future__ import annotations

from ..types import AudioResponse, BuiltinVoice, SavedVoice


class _VoicesBase:
    _list_path = "/v1/voices"
    _builtin_path = "/v1/voices/builtin"


class VoicesResource(_VoicesBase):
    def __init__(self, http: object) -> None:
        self._http = http

    def builtin(self) -> list[BuiltinVoice]:
        """List the pre-defined sample voices (id + name + description).
        Stable; safe to cache client-side."""
        data = self._http.request("GET", self._builtin_path)  # type: ignore[attr-defined]
        return [BuiltinVoice.model_validate(v) for v in data.get("voices", [])]

    def list(self) -> list[SavedVoice]:
        """List the caller's saved voices (both cloned and designed)."""
        data = self._http.request("GET", self._list_path)  # type: ignore[attr-defined]
        return [SavedVoice.model_validate(v) for v in data.get("voices", [])]

    def get(self, voice_id: int) -> SavedVoice:
        """Fetch a single saved voice by id."""
        data = self._http.request("GET", f"{self._list_path}/{voice_id}")  # type: ignore[attr-defined]
        return SavedVoice.model_validate(data.get("voice") or data)

    def delete(self, voice_id: int) -> None:
        """Delete a saved voice."""
        self._http.request("DELETE", f"{self._list_path}/{voice_id}")  # type: ignore[attr-defined]

    def speak(self, voice_id: int, *, text: str) -> AudioResponse:
        """Synthesize ``text`` using a saved voice (cloned or designed)."""
        data = self._http.request(  # type: ignore[attr-defined]
            "POST",
            f"{self._list_path}/{voice_id}/speak",
            json={"text": text},
        )
        return AudioResponse.model_validate(data)


class AsyncVoicesResource(_VoicesBase):
    def __init__(self, http: object) -> None:
        self._http = http

    async def builtin(self) -> list[BuiltinVoice]:
        data = await self._http.request("GET", self._builtin_path)  # type: ignore[attr-defined]
        return [BuiltinVoice.model_validate(v) for v in data.get("voices", [])]

    async def list(self) -> list[SavedVoice]:
        data = await self._http.request("GET", self._list_path)  # type: ignore[attr-defined]
        return [SavedVoice.model_validate(v) for v in data.get("voices", [])]

    async def get(self, voice_id: int) -> SavedVoice:
        data = await self._http.request("GET", f"{self._list_path}/{voice_id}")  # type: ignore[attr-defined]
        return SavedVoice.model_validate(data.get("voice") or data)

    async def delete(self, voice_id: int) -> None:
        await self._http.request("DELETE", f"{self._list_path}/{voice_id}")  # type: ignore[attr-defined]

    async def speak(self, voice_id: int, *, text: str) -> AudioResponse:
        data = await self._http.request(  # type: ignore[attr-defined]
            "POST",
            f"{self._list_path}/{voice_id}/speak",
            json={"text": text},
        )
        return AudioResponse.model_validate(data)
