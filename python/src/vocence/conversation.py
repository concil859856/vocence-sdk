"""High-level voice conversation helper built on top of
:class:`AgentSession`. Useful when you don't care about individual events
and just want "send a turn, get back the assistant's full reply (text +
combined audio)".

For fine-grained control (token-by-token streaming, barge-in, custom
event handling) drop down to the underlying :class:`AgentSession`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ._streaming import AgentEvent, AudioFrame

if TYPE_CHECKING:
    from ._streaming import AgentSession


@dataclass
class Turn:
    """The assistant's full reply for one turn.

    - ``text``       — every ``token`` event concatenated, in order.
    - ``audio``      — every binary audio frame concatenated. Format is in
                       ``audio_meta`` (typically pcm16le 24kHz mono).
    - ``audio_meta`` — the JSON event the server sent right before the
                       first audio frame (sample_rate, frame_ms, encoding,
                       channels). ``None`` if no audio was produced.
    - ``transcript`` — the user-side transcript echoed by the server for
                       voice turns. Empty for text-only turns.
    - ``tool_calls`` — list of ``(name, arguments)`` tuples for each tool
                       call the LLM made this turn.
    - ``events``     — every JSON event in arrival order, in case you
                       need something we didn't surface here.
    """

    text: str = ""
    audio: bytes = b""
    audio_meta: dict[str, Any] | None = None
    transcript: str = ""
    tool_calls: list[tuple[str, str]] = field(default_factory=list)
    events: list[AgentEvent] = field(default_factory=list)


class Conversation:
    """Wraps an :class:`AgentSession` with batched turn semantics.

    Use through :meth:`AsyncVocence.agents.conversation`::

        async with client.agents.conversation("agent-id") as conv:
            turn = await conv.say("What's the weather in Tokyo?")
            print(turn.text)
            with open("reply.pcm", "wb") as f:
                f.write(turn.audio)
    """

    def __init__(self, session: AgentSession) -> None:
        self._session = session

    # The Conversation acts as the context manager itself — opening the
    # underlying session, and forwarding close on exit.
    async def __aenter__(self) -> Conversation:
        await self._session.__aenter__()
        # Drain the initial ``ready`` event so the first say() doesn't
        # see it. We don't need it — connection is open by the time
        # __aenter__ returns.
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self._session.__aexit__(*_exc)

    async def close(self) -> None:
        await self._session.close()

    # ----- turn-level API ----------------------------------------------

    async def say(self, text: str) -> Turn:
        """Send a text turn and block until the assistant's turn_end fires.

        Returns the aggregated :class:`Turn`. Any tool calls happened
        transparently inside the server; you only see the final text +
        audio reply."""
        await self._session.send_text(text)
        return await self._collect_turn()

    async def send_voice(
        self,
        audio_b64: str,
        *,
        mime: str = "audio/webm",
        duration_ms: int | None = None,
    ) -> Turn:
        """Same as :meth:`say` but the user input is an audio clip the
        server should transcribe first."""
        await self._session.send_voice(audio_b64, mime=mime, duration_ms=duration_ms)
        return await self._collect_turn()

    async def _collect_turn(self) -> Turn:
        turn = Turn()
        async for ev in self._session:
            if isinstance(ev, AudioFrame):
                turn.audio += ev.data
                continue
            # JSON event
            turn.events.append(ev)
            t = ev.type
            if t == "token":
                turn.text += str(ev.data.get("text") or "")
            elif t == "transcript":
                turn.transcript += str(ev.data.get("text") or "")
            elif t == "audio_meta":
                turn.audio_meta = {k: v for k, v in ev.data.items() if k != "type"}
            elif t == "tool_call_completed":
                name = str(ev.data.get("name") or "")
                args = str(ev.data.get("arguments") or "")
                turn.tool_calls.append((name, args))
            elif t == "turn_end":
                return turn
        return turn  # connection closed before turn_end — return what we have

    # ----- pass-through ------------------------------------------------

    async def cancel(self) -> None:
        """Barge in — abort the current turn mid-stream."""
        await self._session.cancel()

    def __aiter__(self) -> AsyncIterator[AgentEvent | AudioFrame]:
        """Fallback: iterate the raw event stream, same as
        :class:`AgentSession`. Useful for token-level streaming where
        you don't want to wait for the full turn."""
        return self._session.__aiter__()


__all__ = ["Conversation", "Turn"]
