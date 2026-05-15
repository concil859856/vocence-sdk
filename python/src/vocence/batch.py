"""Concurrency helpers for batch-firing TTS / STT / clone jobs.

Use :func:`tts_speak` or :func:`tts_generate` when you need to synthesize
many clips (an audiobook chapter list, a survey, prerecorded prompts).
The helpers respect the configured rate limit by capping in-flight
requests at ``max_concurrency`` and surface per-item failures as
:class:`BatchError` entries so one bad row doesn't kill the run.

Example
-------

.. code-block:: python

    import asyncio
    from vocence import AsyncVocence, batch

    async def main():
        async with AsyncVocence() as client:
            items = [
                {"text": chunk, "voice": "design-aria"}
                for chunk in chapters
            ]
            results = await batch.tts_speak(client, items, max_concurrency=4)
            for i, r in enumerate(results):
                if isinstance(r, batch.BatchError):
                    print(f"chapter {i}: {r}")
                else:
                    r.write_wav(f"out/{i:03d}.wav")

    asyncio.run(main())
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

from .types import TtsResponse

T = TypeVar("T")


@dataclass
class BatchError:
    """Wraps an exception thrown by one item in a batch, alongside the
    item's index + payload so callers can identify what went wrong
    without re-running the whole batch."""

    index: int
    item: Any
    exception: BaseException

    def __repr__(self) -> str:
        cls = type(self.exception).__name__
        return f"BatchError(index={self.index}, {cls}: {self.exception})"


async def gather_capped(
    items: Sequence[T],
    work: Callable[[T], Awaitable[Any]],
    *,
    max_concurrency: int = 4,
) -> list[Any]:
    """Run ``work(item)`` for every item, capped at ``max_concurrency``
    concurrent tasks. Returns results in the input order; failures are
    wrapped in :class:`BatchError`."""
    semaphore = asyncio.Semaphore(max_concurrency)
    results: list[Any] = [None] * len(items)

    async def runner(i: int, item: T) -> None:
        async with semaphore:
            try:
                results[i] = await work(item)
            except BaseException as e:  # noqa: BLE001 — wrapped for caller
                results[i] = BatchError(index=i, item=item, exception=e)

    await asyncio.gather(*(runner(i, it) for i, it in enumerate(items)))
    return results


async def tts_speak(
    client: Any,
    items: Sequence[dict[str, Any]],
    *,
    max_concurrency: int = 4,
) -> list[TtsResponse | BatchError]:
    """Batch ``client.tts.speak(**item)`` calls.

    Each ``item`` is a dict of kwargs accepted by
    :meth:`AsyncTtsResource.speak` (``text`` + ``voice`` are required;
    ``timeout`` is optional).
    """

    async def one(item: dict[str, Any]) -> TtsResponse:
        return await client.tts.speak(**item)

    return await gather_capped(items, one, max_concurrency=max_concurrency)


async def tts_generate(
    client: Any,
    items: Sequence[dict[str, Any]],
    *,
    max_concurrency: int = 4,
) -> list[TtsResponse | BatchError]:
    """Batch ``client.tts.generate(**item)`` calls."""

    async def one(item: dict[str, Any]) -> TtsResponse:
        return await client.tts.generate(**item)

    return await gather_capped(items, one, max_concurrency=max_concurrency)


async def stt_transcribe(
    client: Any,
    items: Sequence[dict[str, Any]],
    *,
    max_concurrency: int = 4,
) -> list[Any]:
    """Batch ``client.stt.transcribe(**item)`` calls."""

    async def one(item: dict[str, Any]) -> Any:
        return await client.stt.transcribe(**item)

    return await gather_capped(items, one, max_concurrency=max_concurrency)


__all__ = [
    "BatchError",
    "gather_capped",
    "stt_transcribe",
    "tts_generate",
    "tts_speak",
]
