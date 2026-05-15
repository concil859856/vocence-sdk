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
from dataclasses import dataclass
from typing import Any, AsyncIterator

import websockets
from websockets.exceptions import ConnectionClosed

from ._errors import APIConnectionError, AuthenticationError, NotFoundError, UpstreamError, VocenceError


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
    """

    def __init__(self, *, url: str, api_key: str) -> None:
        self._url = url
        self._api_key = api_key.strip()
        if self._api_key.lower().startswith("bearer "):
            self._api_key = self._api_key[7:].strip()
        self._ws: websockets.WebSocketClientProtocol | None = None

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
        """Barge in — abort the current turn mid-stream."""
        await self._send({"type": "cancel"})

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
