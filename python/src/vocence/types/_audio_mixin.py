"""Shared mixin for response shapes that carry an ``audio_url``.

Pulling this onto every audio-returning response (TTS, voice clone,
saved-voice speak) so users don't have to write the ``httpx.get(...).
content`` boilerplate on every script."""

from __future__ import annotations

from pathlib import Path

import httpx


class _AudioFetchMixin:
    """Adds ``.download()`` + ``.write_wav()`` helpers.

    Requires the implementing class to expose an ``audio_url`` field.
    """

    audio_url: str

    def download(self, *, timeout: float = 60.0) -> bytes:
        """Fetch the audio bytes from the presigned URL. The URL has a
        short TTL (typically minutes), so call this soon after the
        response arrives. Raises ``httpx.HTTPError`` subclasses on
        network / non-2xx responses."""
        resp = httpx.get(self.audio_url, timeout=timeout)
        resp.raise_for_status()
        return resp.content

    def write_wav(self, path: str | Path, *, timeout: float = 60.0) -> Path:
        """Download the audio and save it to ``path``. Returns the
        resolved ``Path``. The server already serves WAV-shaped bytes
        for these endpoints (we don't re-mux), so this is a thin
        download + write wrapper."""
        blob = self.download(timeout=timeout)
        p = Path(path)
        p.write_bytes(blob)
        return p
