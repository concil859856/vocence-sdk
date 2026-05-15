"""Shared response shapes — TTS / STT / Voice Clone."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow")


class TtsResponse(_Base):
    """Shape returned by ``POST /v1/tts/generate`` and ``POST /v1/tts/speak``."""

    request_id: str
    audio_url: str
    provider: str
    credits_remaining: int
    latency_ms: int
    credits_used: int
    request_chars: int


class SttResponse(_Base):
    """Shape returned by ``POST /v1/stt/transcribe``."""

    request_id: str
    text: str
    language: str | None = None
    provider: str
    credits_remaining: int
    latency_ms: int
    credits_used: int


class CloneResponse(_Base):
    """Shape returned by ``POST /v1/voice/clone``."""

    request_id: str
    audio_url: str
    reference_text: str
    language: str | None = None
    provider: str
    credits_remaining: int
    latency_ms: int
    credits_used: int


class AudioResponse(_Base):
    """Generic shape returned by saved-voice / sample-voice speak endpoints
    (``POST /v1/voices/{id}/speak``). The dashboard-backend's response is
    passed through verbatim — common keys are typed, anything extra is
    preserved in the model's ``model_extra`` dict.
    """

    audio_url: str
    expires_at: str | None = None
    credits: int | None = None
    reference_text: str | None = None
    detected_language: str | None = None
