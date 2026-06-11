"""Sync wrapper around the async :class:`AgentSession`.

For scripts that don't want to deal with asyncio. We run an internal
event-loop in a background thread and bridge the async iterator into a
plain blocking iterator. The thread is torn down on ``close()``/exit.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from collections.abc import Iterator
from typing import Any

from ._errors import VocenceError
from ._streaming import AgentEvent, AgentSession, AudioFrame

_SENTINEL = object()


class SyncAgentSession:
    """Blocking flavour of :class:`AgentSession`.

    Use as a regular context manager::

        with client.agents.session_sync("agent-id") as sess:
            sess.send_text("hi")
            for event in sess:
                print(event)
                if event.type == "turn_end":
                    break
    """

    def __init__(self, *, url: str, api_key: str) -> None:
        self._url = url
        self._api_key = api_key
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._session: AgentSession | None = None
        self._events: queue.Queue[Any] = queue.Queue()
        self._exc: BaseException | None = None
        self._closed = threading.Event()

    # ----- lifecycle -----------------------------------------------------

    def __enter__(self) -> SyncAgentSession:
        ready = threading.Event()

        def runner() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._run(ready))
            finally:
                # Unblock __enter__ if we crashed before signalling ready.
                ready.set()
                try:
                    self._loop.close()
                except Exception:
                    pass

        self._thread = threading.Thread(target=runner, daemon=True, name="vocence-ws")
        self._thread.start()
        ready.wait()
        if self._exc is not None:
            raise self._exc
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._loop is None or self._closed.is_set():
            return
        self._closed.set()
        if self._session is not None:
            asyncio.run_coroutine_threadsafe(self._session.close(), self._loop)
        if self._thread is not None:
            self._thread.join(timeout=5)

    # ----- background coroutine ------------------------------------------

    async def _run(self, ready: threading.Event) -> None:
        try:
            async with AgentSession(url=self._url, api_key=self._api_key) as sess:
                self._session = sess
                ready.set()
                async for event in sess:
                    if self._closed.is_set():
                        break
                    self._events.put(event)
        except BaseException as e:  # noqa: BLE001 — surfaced via _exc
            # Set the exception BEFORE pushing the sentinel so the
            # consumer can never see the sentinel without also seeing the
            # exception. ``queue.put`` provides the memory barrier.
            self._exc = e
        finally:
            self._events.put(_SENTINEL)

    # ----- outbound ------------------------------------------------------

    def send_text(self, text: str) -> None:
        self._call(lambda s: s.send_text(text))

    def send_voice(self, audio_b64: str, *, mime: str = "audio/webm", duration_ms: int | None = None) -> None:
        self._call(lambda s: s.send_voice(audio_b64, mime=mime, duration_ms=duration_ms))

    def cancel(self) -> None:
        self._call(lambda s: s.cancel())

    def notify_audio_started(self) -> None:
        """See :meth:`AgentSession.notify_audio_started`."""
        self._call(lambda s: s.notify_audio_started())

    def notify_audio_settled(self) -> None:
        """See :meth:`AgentSession.notify_audio_settled`."""
        self._call(lambda s: s.notify_audio_settled())

    def _call(self, factory: Any) -> None:
        if self._session is None or self._loop is None:
            raise VocenceError("Session not started — use `with client.agents.session_sync(...) as sess:`.")
        fut = asyncio.run_coroutine_threadsafe(factory(self._session), self._loop)
        fut.result(timeout=30)

    # ----- inbound -------------------------------------------------------

    def __iter__(self) -> Iterator[AgentEvent | AudioFrame]:
        while True:
            item = self._events.get()
            if item is _SENTINEL:
                if self._exc is not None:
                    raise self._exc
                return
            yield item
