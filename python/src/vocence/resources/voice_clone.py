"""Voice-clone endpoints — one-shot ``POST /v1/voice/clone`` and the
upload-and-save variant ``POST /v1/voice/clone/save``."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import IO, Any

import httpx

from ..types import CloneResponse
from .stt import _b64_audio


def _fetch_url_as_b64(url: str, *, timeout: float = 60.0) -> str:
    """Download a remote audio file and return base64-encoded bytes.

    Used so callers can pass ``audio_url="https://..."`` to the clone
    endpoints when the audio is already hosted somewhere (S3, R2,
    Cloudflare, the user's own CDN). We do the fetch client-side so
    the server doesn't have to whitelist outbound HTTP destinations."""
    resp = httpx.get(url, timeout=timeout)
    resp.raise_for_status()
    return base64.b64encode(resp.content).decode("ascii")


def _normalize_audio_source(
    *,
    audio_path: str | Path | None,
    audio_file: IO[bytes] | None,
    audio_bytes: bytes | None,
    audio_b64: str | None,
    audio_url: str | None,
) -> str:
    """Pick exactly one of the five ways to supply audio and return it
    as base64. Raises ``ValueError`` if zero or more than one source
    is provided. ``audio_url`` is fetched client-side."""
    sources = [s is not None for s in (audio_path, audio_file, audio_bytes, audio_b64, audio_url)]
    if sum(sources) != 1:
        raise ValueError(
            "Supply exactly one of: audio_path, audio_file, audio_bytes, audio_b64, audio_url."
        )
    if audio_url is not None:
        return _fetch_url_as_b64(audio_url)
    return _b64_audio(
        audio_path=audio_path,
        audio_file=audio_file,
        audio_bytes=audio_bytes,
        audio_b64=audio_b64,
    )


class _VoiceCloneBase:
    _create_path = "/v1/voice/clone"
    _save_path = "/v1/voice/clone/save"


def _open_audio_for_upload(
    *,
    audio_path: str | Path | None,
    audio_file: IO[bytes] | None,
    audio_bytes: bytes | None,
    filename: str | None,
    content_type: str,
) -> tuple[str, bytes, str]:
    """Normalize the three ways a caller can supply audio for multipart
    upload into the ``(filename, bytes, content_type)`` tuple httpx wants."""
    sources = [s is not None for s in (audio_path, audio_file, audio_bytes)]
    if sum(sources) != 1:
        raise ValueError("Supply exactly one of: audio_path, audio_file, audio_bytes.")
    if audio_bytes is not None:
        return filename or "clip.wav", audio_bytes, content_type
    if audio_file is not None:
        return filename or getattr(audio_file, "name", "clip.wav"), audio_file.read(), content_type
    assert audio_path is not None
    p = Path(audio_path)
    return filename or p.name, p.read_bytes(), content_type


class VoiceCloneResource(_VoiceCloneBase):
    def __init__(self, http: object) -> None:
        self._http = http

    def create(
        self,
        *,
        target_text: str,
        audio_path: str | Path | None = None,
        audio_file: IO[bytes] | None = None,
        audio_bytes: bytes | None = None,
        audio_b64: str | None = None,
        audio_url: str | None = None,
        language: str | None = None,
        timeout: float | None = None,
    ) -> CloneResponse:
        """One-shot clone: transcribe the reference clip server-side and
        synthesize ``target_text`` in that voice. The reference clip is
        NOT persisted — see :meth:`save` for that.

        Audio source: pass **exactly one** of ``audio_path``,
        ``audio_file``, ``audio_bytes``, ``audio_b64``, or ``audio_url``.
        URLs are fetched client-side so the server doesn't have to be
        whitelisted to reach your storage bucket."""
        body: dict[str, object] = {
            "reference_audio_b64": _normalize_audio_source(
                audio_path=audio_path,
                audio_file=audio_file,
                audio_bytes=audio_bytes,
                audio_b64=audio_b64,
                audio_url=audio_url,
            ),
            "target_text": target_text,
        }
        if language is not None:
            body["language"] = language
        data = self._http.request("POST", self._create_path, json=body, timeout=timeout)  # type: ignore[attr-defined]
        return CloneResponse.model_validate(data)

    def save(
        self,
        *,
        display_name: str,
        audio_path: str | Path | None = None,
        audio_file: IO[bytes] | None = None,
        audio_bytes: bytes | None = None,
        filename: str | None = None,
        content_type: str = "audio/wav",
        language: str | None = None,
        reference_text: str | None = None,
    ) -> dict[str, Any]:
        """Upload a reference clip and store it as a reusable voice. The
        returned dict carries ``voice_id`` you can pass anywhere else
        (e.g. ``client.voices.speak(voice_id, ...)``)."""
        fname, blob, ctype = _open_audio_for_upload(
            audio_path=audio_path,
            audio_file=audio_file,
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=content_type,
        )
        files = {"audio_file": (fname, blob, ctype)}
        data: dict[str, Any] = {"display_name": display_name}
        if language is not None:
            data["language"] = language
        if reference_text is not None:
            data["reference_text"] = reference_text
        return self._http.request("POST", self._save_path, files=files, data=data)  # type: ignore[attr-defined]


class AsyncVoiceCloneResource(_VoiceCloneBase):
    def __init__(self, http: object) -> None:
        self._http = http

    async def create(
        self,
        *,
        target_text: str,
        audio_path: str | Path | None = None,
        audio_file: IO[bytes] | None = None,
        audio_bytes: bytes | None = None,
        audio_b64: str | None = None,
        audio_url: str | None = None,
        language: str | None = None,
        timeout: float | None = None,
    ) -> CloneResponse:
        body: dict[str, object] = {
            "reference_audio_b64": _normalize_audio_source(
                audio_path=audio_path,
                audio_file=audio_file,
                audio_bytes=audio_bytes,
                audio_b64=audio_b64,
                audio_url=audio_url,
            ),
            "target_text": target_text,
        }
        if language is not None:
            body["language"] = language
        data = await self._http.request("POST", self._create_path, json=body, timeout=timeout)  # type: ignore[attr-defined]
        return CloneResponse.model_validate(data)

    async def save(
        self,
        *,
        display_name: str,
        audio_path: str | Path | None = None,
        audio_file: IO[bytes] | None = None,
        audio_bytes: bytes | None = None,
        filename: str | None = None,
        content_type: str = "audio/wav",
        language: str | None = None,
        reference_text: str | None = None,
    ) -> dict[str, Any]:
        fname, blob, ctype = _open_audio_for_upload(
            audio_path=audio_path,
            audio_file=audio_file,
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=content_type,
        )
        files = {"audio_file": (fname, blob, ctype)}
        data: dict[str, Any] = {"display_name": display_name}
        if language is not None:
            data["language"] = language
        if reference_text is not None:
            data["reference_text"] = reference_text
        return await self._http.request("POST", self._save_path, files=files, data=data)  # type: ignore[attr-defined]
