"""Streaming STT WebSocket — ``client.stt.stream(...)``.

A thin async context manager around the
``wss://api.vocence.ai/v1/stt/stream`` endpoint. Push PCM16LE @ 16 kHz
mono frames; receive partial + final transcripts as they're produced
by the Parakeet pod.

Typical usage::

    async with client.stt.stream(language="English") as sess:
        # background task: ship microphone PCM frames
        async def pump():
            async for frame in mic.frames(rate=16000, mono=True, dtype="int16"):
                await sess.send_pcm(frame)
        asyncio.create_task(pump())

        async for event in sess:
            if event.type == "transcript":
                if event.is_final:
                    print("FINAL:", event.text)
                else:
                    print("partial:", event.text)
            elif event.type == "end":
                break

When you're done capturing audio, call :meth:`finish` (or simply leave
the context) — the server flushes a final transcript and closes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from ._errors import APIConnectionError
from ._streaming import _build_close_code_error, _err_for_handshake


@dataclass
class SttStreamEvent:
    """One JSON frame from the server. Common fields surface as
    attributes (``event.text``, ``event.is_final``, ``event.event``)."""

    type: str
    payload: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        if name in self.payload:
            return self.payload[name]
        raise AttributeError(name)


class SttStreamSession:
    """Async context manager wrapping a streaming-STT WebSocket."""

    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        language: str = "English",
        sample_rate: int = 16000,
        encoding: str = "pcm_s16le",
        enable_partials: bool = True,
        vad_events: bool = False,
    ) -> None:
        self._url = url
        key = api_key.strip()
        if key.lower().startswith("bearer "):
            key = key[7:].strip()
        self._api_key = key
        self._start_frame = {
            "type": "start",
            "language": language,
            "sample_rate": int(sample_rate),
            "encoding": encoding,
            "enable_partials": bool(enable_partials),
            "vad_events": bool(vad_events),
        }
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._started = False

    async def __aenter__(self) -> SttStreamSession:
        try:
            self._ws = await websockets.connect(
                self._url,
                additional_headers={"Authorization": f"Bearer {self._api_key}"},
                max_size=8 * 1024 * 1024,
            )
        except websockets.InvalidStatus as e:
            status = getattr(e.response, "status_code", None) or 0
            raise _err_for_handshake(status, str(e)) from e
        except OSError as e:
            raise APIConnectionError(str(e)) from e
        # Fire the start frame immediately — the server expects it as
        # the very first message and won't accept PCM bytes until it's
        # received and responded with ``ready``.
        import json as _json
        await self._ws.send(_json.dumps(self._start_frame))
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.finish()

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def finish(self) -> None:
        """Signal end-of-audio. The server flushes any in-progress
        transcript, emits ``{"type":"end"}`` and closes. Safe to call
        more than once."""
        import json as _json
        if self._ws is not None:
            try:
                await self._ws.send(_json.dumps({"type": "stop"}))
            except Exception:
                pass

    # ----- outbound ------------------------------------------------------

    async def send_pcm(self, pcm: bytes) -> None:
        """Push one PCM16LE frame. The wire protocol doesn't dictate a
        specific frame length — 20–60 ms is typical. Streaming straight
        from a mic capture loop is fine; the WS layer batches at the
        TCP level."""
        if not self._ws:
            raise APIConnectionError("session not open — use as async context manager")
        if not isinstance(pcm, (bytes, bytearray, memoryview)):
            raise TypeError("send_pcm expects bytes-like, got " + type(pcm).__name__)
        await self._ws.send(bytes(pcm))

    # ----- inbound -------------------------------------------------------

    def __aiter__(self) -> AsyncIterator[SttStreamEvent]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[SttStreamEvent]:
        import json as _json
        if not self._ws:
            raise APIConnectionError("session not open")
        try:
            while True:
                raw = await self._ws.recv()
                if isinstance(raw, (bytes, bytearray)):
                    # The pod-side protocol shouldn't push binary back —
                    # but if it does, skip rather than crash the iter.
                    continue
                try:
                    data = _json.loads(raw)
                except Exception:
                    continue
                t = str(data.get("type") or "")
                yield SttStreamEvent(type=t, payload=data)
        except ConnectionClosed as e:
            code = getattr(e, "code", 0) or 0
            reason = (getattr(e, "reason", None) or "").strip()
            err = _build_close_code_error(code, reason)
            if err is not None:
                raise err from e
            return
