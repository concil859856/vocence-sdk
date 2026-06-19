"""Voice-design endpoints — generate previews from a written description and
persist the chosen variant. The pipeline generates two TTS variants
internally (original / LLM-revised) but the public API surfaces only the
*original* variant for deterministic API behavior. Pass the returned
``preview_token`` to :meth:`save` to persist the voice for re-use."""

from __future__ import annotations

from typing import Literal

from ..types import VoiceDesignPreview


class _VoiceDesignBase:
    _preview_path = "/v1/voice/design/preview"
    _save_path = "/v1/voice/design/save"


class VoiceDesignResource(_VoiceDesignBase):
    def __init__(self, http: object) -> None:
        self._http = http

    def preview(self, *, voice_description: str) -> VoiceDesignPreview:
        """Generate a TTS preview from a free-form voice description.
        Returns a ``preview_token`` + single ``audio_url``."""
        data = self._http.request(  # type: ignore[attr-defined]
            "POST",
            self._preview_path,
            json={"voice_description": voice_description},
        )
        return VoiceDesignPreview.model_validate(data)

    def save(
        self,
        *,
        preview_token: str,
        chosen_variant: Literal["original", "revised"],
        display_name: str,
    ) -> dict:
        """Persist the chosen preview variant as a reusable voice.
        Returns the new ``voice_id`` and the cached audio URL."""
        return self._http.request(  # type: ignore[attr-defined]
            "POST",
            self._save_path,
            json={
                "preview_token": preview_token,
                "chosen_variant": chosen_variant,
                "display_name": display_name,
            },
        )


class AsyncVoiceDesignResource(_VoiceDesignBase):
    def __init__(self, http: object) -> None:
        self._http = http

    async def preview(self, *, voice_description: str) -> VoiceDesignPreview:
        data = await self._http.request(  # type: ignore[attr-defined]
            "POST",
            self._preview_path,
            json={"voice_description": voice_description},
        )
        return VoiceDesignPreview.model_validate(data)

    async def save(
        self,
        *,
        preview_token: str,
        chosen_variant: Literal["original", "revised"],
        display_name: str,
    ) -> dict:
        return await self._http.request(  # type: ignore[attr-defined]
            "POST",
            self._save_path,
            json={
                "preview_token": preview_token,
                "chosen_variant": chosen_variant,
                "display_name": display_name,
            },
        )
