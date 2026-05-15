"""Mic-in / speaker-out wrapper around the async voice agent session.

Push-to-talk model (simplest, most reliable across platforms):

1. Caller presses ``record()``  → start capturing 16-bit PCM from the
   default input device at 16 kHz mono.
2. Caller presses ``stop()``    → close the capture stream, wrap the
   buffered PCM into a WAV blob, base64-encode it, send as a ``voice``
   turn over the WebSocket.
3. Server streams back text + audio frames; we play frames through the
   default output device as they arrive.
4. Repeat.

We intentionally don't try to do continuous streaming or local VAD in
v0.3 — the WS protocol expects a complete clip per turn anyway, and
push-to-talk is what works reliably in a terminal without any GUI to
show a "recording" indicator.

Requires the optional ``vocence[audio]`` extra (``sounddevice`` +
``numpy``).
"""

from __future__ import annotations

import asyncio
import base64
import io
from typing import Any

from ._audio import _require_audio, write_pcm16_to_wav
from ._errors import VocenceError
from ._streaming import AgentEvent, AgentSession, AudioFrame

# Recording sample rate. The voicechat backend transcodes whatever we
# send through Whisper / Qwen3-ASR anyway, but 16 kHz keeps WAV files
# small while still preserving speech clarity.
_REC_RATE = 16000
_REC_CHANNELS = 1


class LiveChat:
    """Async mic↔agent helper. Use as a context manager.

    Example::

        async with client.agents.live_chat("agent-id") as live:
            live.record()
            input("press enter to stop talking…")
            turn = await live.stop_and_send()
            print(turn["text"])

    Or the one-shot form::

        async with client.agents.live_chat("agent-id") as live:
            turn = await live.say_press_enter_to_stop()
    """

    def __init__(self, session: AgentSession) -> None:
        self._session = session
        self._sd = None  # lazy-loaded sounddevice module
        self._np = None  # lazy-loaded numpy module
        self._stream = None  # active InputStream (None when not recording)
        self._frames: list[Any] = []  # numpy arrays appended in the callback

    async def __aenter__(self) -> LiveChat:
        self._sd, self._np = _require_audio()
        await self._session.__aenter__()
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
        except Exception:
            pass
        await self._session.__aexit__(*_exc)

    # ----- microphone ----------------------------------------------------

    def record(self) -> None:
        """Begin capturing from the default mic. Non-blocking — call
        :meth:`stop_and_send` to finish the turn."""
        if self._stream is not None:
            return
        assert self._sd is not None and self._np is not None
        self._frames = []

        def callback(indata, _frames, _time, _status) -> None:  # noqa: ANN001
            # Copy the chunk; sounddevice reuses the buffer next call.
            self._frames.append(indata.copy())

        self._stream = self._sd.InputStream(
            samplerate=_REC_RATE,
            channels=_REC_CHANNELS,
            dtype="int16",
            callback=callback,
        )
        self._stream.start()

    async def stop_and_send(self, *, language: str | None = None) -> dict[str, Any]:
        """Stop the mic, ship the clip, wait for ``turn_end``, return a
        dict ``{text, audio, audio_meta, transcript, events}``."""
        if self._stream is None:
            raise VocenceError("record() was never called.")
        assert self._np is not None
        self._stream.stop()
        self._stream.close()
        self._stream = None

        if not self._frames:
            raise VocenceError("Mic produced no frames — is the input device working?")
        pcm_arr = self._np.concatenate(self._frames, axis=0)
        pcm_bytes = pcm_arr.tobytes()
        wav_buf = io.BytesIO()
        write_pcm16_to_wav(pcm_bytes, wav_buf, sample_rate=_REC_RATE, channels=_REC_CHANNELS)
        b64 = base64.b64encode(wav_buf.getvalue()).decode("ascii")

        await self._session.send_voice(
            b64,
            mime="audio/wav",
            duration_ms=int(len(pcm_arr) / _REC_RATE * 1000),
        )
        return await self._collect_and_play(language=language)

    async def _collect_and_play(self, *, language: str | None) -> dict[str, Any]:
        """Iterate events until ``turn_end``; play each audio frame as
        it arrives so playback overlaps the LLM streaming."""
        sd = self._sd
        assert sd is not None
        result_text = ""
        result_transcript = ""
        audio_bytes = b""
        audio_meta: dict[str, Any] | None = None
        events: list[AgentEvent] = []
        out_stream = None

        async for ev in self._session:
            if isinstance(ev, AudioFrame):
                if out_stream is None:
                    # Open the speaker stream lazily once we know the format.
                    sr = int((audio_meta or {}).get("sample_rate") or 24000)
                    ch = int((audio_meta or {}).get("channels") or 1)
                    out_stream = sd.RawOutputStream(samplerate=sr, channels=ch, dtype="int16")
                    out_stream.start()
                out_stream.write(ev.data)
                audio_bytes += ev.data
                continue

            events.append(ev)
            t = ev.type
            if t == "token":
                result_text += str(ev.data.get("text") or "")
            elif t == "transcript":
                result_transcript += str(ev.data.get("text") or "")
            elif t == "audio_meta":
                audio_meta = {k: v for k, v in ev.data.items() if k != "type"}
            elif t == "turn_end":
                break

        if out_stream is not None:
            # Give PortAudio a beat to drain the buffer before we close.
            await asyncio.sleep(0.1)
            out_stream.stop()
            out_stream.close()
        return {
            "text": result_text,
            "transcript": result_transcript,
            "audio": audio_bytes,
            "audio_meta": audio_meta,
            "events": events,
        }

    # ----- one-shot convenience -----------------------------------------

    async def say_press_enter_to_stop(self, prompt: str = "press enter to stop talking…") -> dict[str, Any]:
        """Record until the user presses Enter, then send + play the
        reply. Useful for the simplest possible REPL."""
        self.record()
        await asyncio.get_event_loop().run_in_executor(None, input, prompt)
        return await self.stop_and_send()

    # ----- text fallback ------------------------------------------------

    async def say_text(self, text: str) -> dict[str, Any]:
        """Send a typed turn instead of speaking — handy for testing
        without a microphone, or in mixed text/voice flows."""
        await self._session.send_text(text)
        return await self._collect_and_play(language=None)
