"""Streaming TTS WebSocket — ``client.tts.stream(voice_id)``.

A thin async context manager around the
``wss://api.vocence.ai/v1/voices/{voice_id}/stream`` endpoint. Use
when you want low-latency PCM frames flowing as the server generates
audio, rather than waiting for the whole clip via ``tts.speak`` or
the saved-voice HTTP endpoint.

Typical usage::

    async with client.tts.stream(voice_id=42) as sess:
        await sess.speak("Hello there, this is streaming.")
        async for event in sess:
            if event.type == "meta":
                rate = event.sample_rate          # 24000
                encoding = event.encoding         # 'pcm_s16le'
            elif event.type == "audio":
                play_or_buffer(event.data)        # bytes
            elif event.type == "end":
                break

``voice_id`` is the integer id of a saved voice (designed or
cloned). The first event you'll see after :meth:`speak` is a
``meta`` frame with the audio format, followed by ``audio`` frames
(raw PCM bytes) and a terminal ``end`` frame.

Multiple ``speak`` calls on the same session are fine — each fires
a fresh meta/audio/end sequence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator

import websockets
from websockets.exceptions import ConnectionClosed

from ._errors import APIConnectionError
from ._streaming import _build_close_code_error, _err_for_handshake


@dataclass
class TtsStreamEvent:
    """One frame from the server.

    The ``type`` is ``"meta"`` (audio format announcement), ``"audio"``
    (raw PCM bytes in :attr:`data`), ``"end"`` (utterance done — you
    can call :meth:`speak` again on the same session), or ``"error"``.
    """

    type: str
    data: bytes | None = None
    payload: dict[str, Any] | None = None

    def __getattr__(self, name: str) -> Any:
        # Passthrough convenience: event.sample_rate, event.encoding, etc.
        if self.payload and name in self.payload:
            return self.payload[name]
        raise AttributeError(name)


class TtsStreamSession:
    """Async context manager wrapping a streaming-TTS WebSocket."""

    def __init__(self, *, url: str, api_key: str) -> None:
        self._url = url
        key = api_key.strip()
        if key.lower().startswith("bearer "):
            key = key[7:].strip()
        self._api_key = key
        self._ws: websockets.WebSocketClientProtocol | None = None

    async def __aenter__(self) -> "TtsStreamSession":
        try:
            self._ws = await websockets.connect(
                self._url,
                additional_headers={"Authorization": f"Bearer {self._api_key}"},
                # PCM frames can be sizable on a long utterance — be
                # generous with the per-frame ceiling.
                max_size=8 * 1024 * 1024,
            )
        except websockets.InvalidStatus as e:
            status = getattr(e.response, "status_code", None) or 0
            raise _err_for_handshake(status, str(e)) from e
        except OSError as e:
            raise APIConnectionError(str(e)) from e
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    # ----- outbound ------------------------------------------------------

    async def speak(self, text: str, *, language: str | None = None) -> None:
        """Kick off one synthesis turn. Yields audio frames via the
        iterator until an ``end`` event arrives. Calling speak before
        the previous turn's ``end`` is a protocol violation — wait
        for ``end`` before re-firing."""
        import json as _json
        if not self._ws:
            raise APIConnectionError("session not open — use as async context manager")
        payload: dict[str, Any] = {"type": "speak", "text": text}
        if language is not None:
            payload["language"] = language
        await self._ws.send(_json.dumps(payload))

    async def stop(self) -> None:
        """Close the session cleanly. Equivalent to ``await session.close()``
        but emits the explicit ``stop`` frame first so the server can
        flush any in-flight billing / log rows."""
        import json as _json
        if self._ws is not None:
            try:
                await self._ws.send(_json.dumps({"type": "stop"}))
            except Exception:
                pass
        await self.close()

    # ----- inbound -------------------------------------------------------

    def __aiter__(self) -> AsyncIterator[TtsStreamEvent]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[TtsStreamEvent]:
        import json as _json
        if not self._ws:
            raise APIConnectionError("session not open")
        try:
            while True:
                raw = await self._ws.recv()
                if isinstance(raw, (bytes, bytearray)):
                    yield TtsStreamEvent(type="audio", data=bytes(raw))
                    continue
                # Text frame — JSON event.
                try:
                    data = _json.loads(raw)
                except Exception:
                    continue
                t = str(data.get("type") or "")
                yield TtsStreamEvent(type=t, payload=data)
        except ConnectionClosed as e:
            code = getattr(e, "code", 0) or 0
            reason = (getattr(e, "reason", None) or "").strip()
            err = _build_close_code_error(code, reason)
            if err is not None:
                raise err from e
            return
