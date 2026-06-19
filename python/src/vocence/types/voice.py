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

    The pipeline generates two TTS variants internally (one matching the
    prompt verbatim, one with an LLM-polished version) but the public
    API surfaces only the **original** variant for deterministic
    behavior — the same description yields the same audio across calls.
    Website users see both variants for A/B testing; API consumers get
    a single result.

    Pass ``preview_token`` to ``POST /v1/voice/design/save`` to persist
    this voice for re-use.
    """

    preview_token: str
    audio_url: str
    voice_description: str
    revised_instruction: str | None = None
    credits_used: int | None = None
    credits_remaining: int | None = None
