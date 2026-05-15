"""Speech-to-text endpoint — ``POST /v1/stt/transcribe``."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import IO

from ..types import SttResponse


def _b64_audio(
    *,
    audio_path: str | Path | None,
    audio_file: IO[bytes] | None,
    audio_bytes: bytes | None,
    audio_b64: str | None,
) -> str:
    """Normalize the four ways a caller can supply audio into a single
    base64 string. Raises ``ValueError`` if zero or more than one source
    was provided."""
    sources = [s is not None for s in (audio_path, audio_file, audio_bytes, audio_b64)]
    if sum(sources) != 1:
        raise ValueError("Supply exactly one of: audio_path, audio_file, audio_bytes, audio_b64.")
    if audio_b64 is not None:
        return audio_b64
    if audio_bytes is not None:
        return base64.b64encode(audio_bytes).decode("ascii")
    if audio_file is not None:
        return base64.b64encode(audio_file.read()).decode("ascii")
    assert audio_path is not None
    raw = Path(audio_path).read_bytes()
    return base64.b64encode(raw).decode("ascii")


class _SttBase:
    _path = "/v1/stt/transcribe"


class SttResource(_SttBase):
    def __init__(self, http: object) -> None:
        self._http = http

    def transcribe(
        self,
        *,
        audio_path: str | Path | None = None,
        audio_file: IO[bytes] | None = None,
        audio_bytes: bytes | None = None,
        audio_b64: str | None = None,
        language: str | None = None,
    ) -> SttResponse:
        """Transcribe an audio clip. Supply the audio in exactly one of
        four ways — ``audio_path`` (read from disk), ``audio_file`` (file
        handle), ``audio_bytes`` (raw bytes already in memory), or
        ``audio_b64`` (pre-encoded). Hard cap: 50 MB encoded."""
        body: dict[str, object] = {
            "audio_b64": _b64_audio(
                audio_path=audio_path,
                audio_file=audio_file,
                audio_bytes=audio_bytes,
                audio_b64=audio_b64,
            ),
        }
        if language is not None:
            body["language"] = language
        data = self._http.request("POST", self._path, json=body)  # type: ignore[attr-defined]
        return SttResponse.model_validate(data)


class AsyncSttResource(_SttBase):
    def __init__(self, http: object) -> None:
        self._http = http

    async def transcribe(
        self,
        *,
        audio_path: str | Path | None = None,
        audio_file: IO[bytes] | None = None,
        audio_bytes: bytes | None = None,
        audio_b64: str | None = None,
        language: str | None = None,
    ) -> SttResponse:
        body: dict[str, object] = {
            "audio_b64": _b64_audio(
                audio_path=audio_path,
                audio_file=audio_file,
                audio_bytes=audio_bytes,
                audio_b64=audio_b64,
            ),
        }
        if language is not None:
            body["language"] = language
        data = await self._http.request("POST", self._path, json=body)  # type: ignore[attr-defined]
        return SttResponse.model_validate(data)
