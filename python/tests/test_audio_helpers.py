"""TtsResponse.download() / .write_wav() / etc."""

from __future__ import annotations

from pathlib import Path

import httpx
import respx

from vocence.types import AudioResponse, CloneResponse, TtsResponse


_FAKE_WAV = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00@\x1f\x00\x00\x80>\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"


def test_tts_response_download() -> None:
    with respx.mock() as router:
        router.get("https://example/x.wav").mock(return_value=httpx.Response(200, content=_FAKE_WAV))
        r = TtsResponse(
            request_id="r", audio_url="https://example/x.wav", provider="Vocence API",
            credits_remaining=1, latency_ms=1, credits_used=0, request_chars=1,
        )
        assert r.download() == _FAKE_WAV


def test_tts_response_write_wav(tmp_path: Path) -> None:
    with respx.mock() as router:
        router.get("https://example/y.wav").mock(return_value=httpx.Response(200, content=_FAKE_WAV))
        r = TtsResponse(
            request_id="r", audio_url="https://example/y.wav", provider="Vocence API",
            credits_remaining=1, latency_ms=1, credits_used=0, request_chars=1,
        )
        out = r.write_wav(tmp_path / "out.wav")
        assert out.read_bytes() == _FAKE_WAV


def test_clone_response_download() -> None:
    with respx.mock() as router:
        router.get("https://example/c.wav").mock(return_value=httpx.Response(200, content=_FAKE_WAV))
        r = CloneResponse(
            request_id="r", audio_url="https://example/c.wav", reference_text="hi",
            provider="Vocence API", credits_remaining=1, latency_ms=1, credits_used=0,
        )
        assert r.download() == _FAKE_WAV


def test_audio_response_download() -> None:
    with respx.mock() as router:
        router.get("https://example/a.wav").mock(return_value=httpx.Response(200, content=_FAKE_WAV))
        r = AudioResponse(audio_url="https://example/a.wav")
        assert r.download() == _FAKE_WAV
