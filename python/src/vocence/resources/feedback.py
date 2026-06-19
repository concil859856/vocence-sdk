"""Feedback — record thumbs-up / thumbs-down on a generation.

Lets your app capture quality signal on the AI outputs you ship to
your own users. Each rating is keyed on ``(entry_type, entry_id)`` —
pass the same ``entry_id`` you assigned to the generation (job id,
message id, etc.) and the rating is upserted.

    client = Vocence(api_key="voc_live_…")
    # User clicks thumbs-down on a TTS clip
    client.feedback.submit(
        entry_type="tts",
        entry_id="job_abc123",
        rating=-1,
        comment="Voice sounded robotic on long sentences",
    )

    # Later, fetch the current rating for that generation
    state = client.feedback.get(entry_type="tts", entry_id="job_abc123")
    state["rating"]  # -1
    state["comment"]  # "Voice sounded robotic on long sentences"

``rating`` is one of ``-1`` (thumb-down), ``1`` (thumb-up), or ``0``
(clear the rating — "un-vote"). The GET never 404s: when no rating
exists, ``rating`` is returned as ``0`` so callers don't need a
separate branch.

``entry_type`` must be one of:
    tts, stt, voice_clone, voice_design, music, noise_remover,
    agent_call, agent_message
"""

from __future__ import annotations

from typing import Any

# Kept in sync with developer-api/app/api/routes/feedback.py. The
# server validates as well; this is a local guard so the SDK fails
# fast with a clear error instead of a 400 round-trip.
_ALLOWED_ENTRY_TYPES = frozenset({
    "tts", "stt", "voice_clone", "voice_design", "music",
    "noise_remover", "agent_call", "agent_message",
})


def _check_entry_type(entry_type: str) -> None:
    if entry_type not in _ALLOWED_ENTRY_TYPES:
        raise ValueError(
            f"entry_type must be one of {sorted(_ALLOWED_ENTRY_TYPES)}, "
            f"got {entry_type!r}"
        )


def _body(*, entry_type: str, entry_id: str, rating: int, comment: str | None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "entry_type": entry_type,
        "entry_id": entry_id,
        "rating": rating,
    }
    if comment is not None:
        out["comment"] = comment
    return out


# --------------------------------------------------------------------- sync


class FeedbackResource:
    """Sync feedback resource, attached as ``client.feedback``."""

    _path = "/v1/feedback"

    def __init__(self, http: object) -> None:
        self._http = http

    def submit(
        self,
        *,
        entry_type: str,
        entry_id: str,
        rating: int,
        comment: str | None = None,
    ) -> dict:
        """Upsert thumbs on ``(entry_type, entry_id)``.

        ``rating=0`` clears any existing rating for that pair so the
        UI can implement "click again to un-vote" without a separate
        delete endpoint.
        """
        _check_entry_type(entry_type)
        if rating not in (-1, 0, 1):
            raise ValueError(f"rating must be -1, 0, or 1 — got {rating!r}")
        return self._http.request(  # type: ignore[attr-defined]
            "POST", self._path,
            json=_body(entry_type=entry_type, entry_id=entry_id, rating=rating, comment=comment),
        )

    def get(self, *, entry_type: str, entry_id: str) -> dict:
        """Return ``{rating, comment}`` for a single generation. When
        no rating exists, ``rating`` is ``0`` (not a 404)."""
        _check_entry_type(entry_type)
        return self._http.request(  # type: ignore[attr-defined]
            "GET", self._path,
            params={"entry_type": entry_type, "entry_id": entry_id},
        )


# -------------------------------------------------------------------- async


class AsyncFeedbackResource:
    """Async sibling of :class:`FeedbackResource`."""

    _path = "/v1/feedback"

    def __init__(self, http: object) -> None:
        self._http = http

    async def submit(
        self,
        *,
        entry_type: str,
        entry_id: str,
        rating: int,
        comment: str | None = None,
    ) -> dict:
        _check_entry_type(entry_type)
        if rating not in (-1, 0, 1):
            raise ValueError(f"rating must be -1, 0, or 1 — got {rating!r}")
        return await self._http.request(  # type: ignore[attr-defined]
            "POST", self._path,
            json=_body(entry_type=entry_type, entry_id=entry_id, rating=rating, comment=comment),
        )

    async def get(self, *, entry_type: str, entry_id: str) -> dict:
        _check_entry_type(entry_type)
        return await self._http.request(  # type: ignore[attr-defined]
            "GET", self._path,
            params={"entry_type": entry_type, "entry_id": entry_id},
        )
