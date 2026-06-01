"""Async WebSocket session helper for ``/v1/agents/{agent_id}/session``.

Use through :meth:`vocence.AsyncVocence.agents.session`::

    async with client.agents.session("agent-id") as sess:
        await sess.send_text("hello")
        async for event in sess:
            if event.type == "turn_end":
                break

Events come in two flavours: JSON control frames (typed as
:class:`AgentEvent`) and binary audio frames (typed as :class:`AudioFrame`).
The async iterator yields both, in arrival order, until the server closes
the connection or the iterator is cancelled.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from ._errors import (
    APIConnectionError,
    AuthenticationError,
    NotFoundError,
    UpstreamError,
    VocenceError,
)


@dataclass
class AgentEvent:
    """A JSON event from the server.

    The full payload is preserved in :attr:`data`; common keys
    (``type``, ``text``, ``session_id``, ``sentence_id``, ``sample_rate``,
    ``frame_ms``, ``encoding``, ``channels``, ``code``, ``message``)
    are surfaced as attributes for convenience.
    """

    type: str
    data: dict[str, Any]

    def __getattr__(self, name: str) -> Any:  # noqa: D401 — passthrough
        if name in self.data:
            return self.data[name]
        raise AttributeError(name)


@dataclass
class AudioFrame:
    """A binary audio frame. Format is announced by the preceding
    ``audio_meta`` event (typically pcm16le, 24000 Hz, 40 ms, mono)."""

    data: bytes
    type: str = "audio"


_CloseCodeError: dict[int, type[VocenceError]] = {
    4401: AuthenticationError,
    4404: NotFoundError,
    4502: UpstreamError,
    4503: UpstreamError,
}


class AgentSession:
    """Async context manager wrapping a WS connection to one agent.

    Created lazily — the connection is opened on ``__aenter__`` and closed
    on ``__aexit__``. Use :meth:`send_text`, :meth:`send_voice`, or
    :meth:`cancel` to drive the conversation; iterate the session to
    receive server events.

    Three turn modes:

    * ``send_text(...)`` — one-shot text turn.
    * ``send_voice(audio_b64, ...)`` — one-shot WAV upload (works on
      every deployment).
    * ``start_stream()`` / :meth:`send_pcm` / :meth:`commit_stream` —
      live PCM streaming with server-side VAD + turn-detection. Only
      available when ``capabilities['voice_stream']`` is True on the
      ``ready`` event; otherwise fall back to ``send_voice``.

    ``capabilities`` is populated from the server's ``ready`` event the
    first time the session reads one. Call :meth:`wait_ready` to block
    until that arrives before deciding which path to use.
    """

    def __init__(self, *, url: str, api_key: str) -> None:
        self._url = url
        self._api_key = api_key.strip()
        if self._api_key.lower().startswith("bearer "):
            self._api_key = self._api_key[7:].strip()
        self._ws: websockets.WebSocketClientProtocol | None = None
        # Populated from the first ``ready`` event the session sees.
        # Until then this dict is empty — call :meth:`wait_ready` to
        # block on it.
        self.capabilities: dict[str, Any] = {}
        self.session_id: str | None = None
        # Internal: true once a stream_start has been sent and not yet
        # closed by stream_commit / cancel. Guards send_pcm against
        # being called outside an open turn.
        self._stream_open = False
        self._ready_event = None  # asyncio.Event, set on first ready

    async def __aenter__(self) -> AgentSession:
        try:
            self._ws = await websockets.connect(
                self._url,
                additional_headers={"Authorization": f"Bearer {self._api_key}"},
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

    async def send_text(self, text: str) -> None:
        """Send a text turn. Server replies with ``token`` / ``audio_meta`` /
        binary audio frames / ``audio_end`` / ``turn_end``."""
        await self._send({"type": "text", "text": text})

    async def send_voice(
        self,
        audio_b64: str,
        *,
        mime: str = "audio/webm",
        duration_ms: int | None = None,
    ) -> None:
        """Send a base64-encoded audio turn. The server transcribes it and
        treats the transcript as the user's input."""
        payload: dict[str, Any] = {"type": "voice", "audio_b64": audio_b64, "mime": mime}
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        await self._send(payload)

    async def cancel(self) -> None:
        """Barge in — abort the current turn mid-stream. Also clears
        the open-stream flag so a subsequent ``send_pcm`` will refuse."""
        await self._send({"type": "cancel"})
        self._stream_open = False

    async def start_stream(self) -> None:
        """Open a live PCM streaming turn.

        After this returns, push 16 kHz mono ``pcm_s16le`` frames via
        :meth:`send_pcm`. Close the turn with :meth:`commit_stream`
        when the user finishes speaking — or :meth:`cancel` to abort.

        Only valid when ``capabilities['voice_stream']`` is True. Use
        :meth:`wait_ready` first to discover that flag::

            await sess.wait_ready()
            if sess.capabilities.get("voice_stream"):
                await sess.start_stream()
                while ...:
                    await sess.send_pcm(pcm_chunk)
                await sess.commit_stream()
            else:
                await sess.send_voice(wav_b64)
        """
        if self._stream_open:
            raise VocenceError("stream already open — commit or cancel before starting a new turn")
        await self._send({"type": "stream_start"})
        self._stream_open = True

    async def send_pcm(self, frame: bytes) -> None:
        """Push one PCM frame to the open stream.

        Frame format: 16 kHz mono signed-16-bit little-endian raw
        samples. The server's ``capabilities.frame`` block reports the
        preferred frame size in ms (20 ms = 640 bytes); other sizes
        work too but the upstream STT pod buffers internally."""
        if self._ws is None:
            raise VocenceError("Session not started.")
        if not self._stream_open:
            raise VocenceError("No open stream — call start_stream() first.")
        if not isinstance(frame, (bytes, bytearray, memoryview)):
            raise VocenceError("send_pcm expects raw bytes (PCM16LE @ 16 kHz mono).")
        await self._ws.send(bytes(frame))

    async def commit_stream(self) -> None:
        """Tell the server the user finished talking. The server flushes
        STT, runs the LLM, and starts streaming the reply (token + audio)
        as normal."""
        if not self._stream_open:
            raise VocenceError("No open stream to commit.")
        await self._send({"type": "stream_commit"})
        self._stream_open = False

    async def wait_ready(self, timeout: float = 10.0) -> dict[str, Any]:
        """Block until the server's ``ready`` event arrives (or
        ``timeout`` seconds, whichever first). Returns the capabilities
        dict so the caller can decide between streaming and one-shot
        paths.

        Note: calling this consumes events from the WS until ``ready``
        is seen — any earlier events get attached to :attr:`session_id`
        / :attr:`capabilities` rather than yielded by the iterator. Use
        this BEFORE entering the ``async for event in sess`` loop."""
        import asyncio as _asyncio
        if self._ws is None:
            raise VocenceError("Session not started.")
        if self._ready_event is None:
            self._ready_event = _asyncio.Event()

        async def _drain_until_ready() -> None:
            assert self._ws is not None
            async for raw in self._ws:
                if isinstance(raw, (bytes, bytearray)):
                    # Shouldn't arrive before ready in practice — drop.
                    continue
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(msg, dict):
                    continue
                if msg.get("type") == "ready":
                    self.session_id = msg.get("session_id")
                    self.capabilities = dict(msg.get("capabilities") or {})
                    assert self._ready_event is not None
                    self._ready_event.set()
                    return

        try:
            await _asyncio.wait_for(_drain_until_ready(), timeout=timeout)
        except _asyncio.TimeoutError as e:
            raise VocenceError(f"timed out waiting for ready (>{timeout:.1f}s)") from e
        return self.capabilities

    async def _send(self, payload: dict[str, Any]) -> None:
        if self._ws is None:
            raise VocenceError("Session not started — use `async with client.agents.session(...) as sess:`.")
        await self._ws.send(json.dumps(payload))

    # ----- inbound -------------------------------------------------------

    def __aiter__(self) -> AsyncIterator[AgentEvent | AudioFrame]:
        return self._events()

    async def _events(self) -> AsyncIterator[AgentEvent | AudioFrame]:
        if self._ws is None:
            raise VocenceError("Session not started.")
        try:
            async for msg in self._ws:
                if isinstance(msg, (bytes, bytearray)):
                    yield AudioFrame(data=bytes(msg))
                else:
                    try:
                        data = json.loads(msg)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(data, dict):
                        continue
                    # Cache capabilities + session_id off ``ready`` even
                    # when the caller iterates without first calling
                    # ``wait_ready`` — they'll still be available as
                    # ``sess.capabilities`` / ``sess.session_id``.
                    if data.get("type") == "ready":
                        self.session_id = data.get("session_id") or self.session_id
                        caps = data.get("capabilities")
                        if isinstance(caps, dict):
                            self.capabilities = dict(caps)
                    if data.get("type") == "error":
                        # Raise so the user can `except VocenceError`.
                        raise UpstreamError(
                            data.get("message") or "WebSocket error event",
                            detail=data.get("code"),
                            response=data,
                        )
                    yield AgentEvent(type=str(data.get("type") or ""), data=data)
        except ConnectionClosed as e:
            code = getattr(e, "code", 0) or 0
            if code and code in _CloseCodeError:
                raise _CloseCodeError[code](f"WebSocket closed with code {code}") from e
            # Normal close (1000 etc.) just ends the iteration.
            return


def _err_for_handshake(status: int, msg: str) -> VocenceError:
    """Map an HTTP-style WS upgrade failure to a typed SDK exception."""
    from ._errors import error_for_status

    return error_for_status(status, detail=msg, response=None)
