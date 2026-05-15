"""Voice catalog / saved-voice / voice-design types."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow")


class BuiltinVoice(_Base):
    """One entry returned by ``GET /v1/voices/builtin``."""

    id: str
    name: str
    description: str


class SavedVoice(_Base):
    """One entry returned by ``GET /v1/voices`` / ``GET /v1/voices/{id}``.

    ``source`` is either ``"cloned"`` (uploaded clip) or ``"designed"``
    (prompt-based via Voice Design).
    """

    id: int
    display_name: str
    source: str
    ref_script: str | None = None
    voice_description: str | None = None
    source_language: str | None = None
    created_at: str | None = None
    expires_at: str | None = None


class VoiceDesignPreview(_Base):
    """Response from ``POST /v1/voice/design/preview``.

    Two TTS variants are generated from the same description:

    - ``audio_a_url`` — *original* (your prompt verbatim).
    - ``audio_b_url`` — *revised* (LLM-polished version of your prompt).

    Pass ``preview_token`` plus the chosen variant to
    ``POST /v1/voice/design/save`` to persist the winner.
    """

    preview_token: str
    sample_script: str
    voice_description: str
    revised_instruction: str | None = None
    audio_a_url: str
    audio_b_url: str
    expires_at: str | None = None
    credits: int | None = None
