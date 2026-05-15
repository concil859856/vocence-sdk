"""Audio helpers — WAV serialization + optional playback shim."""

from __future__ import annotations

import io
import struct
import wave
from pathlib import Path

import pytest

from vocence._audio import play_pcm16, write_pcm16_to_wav
from vocence.conversation import Turn


def _two_seconds_of_silence() -> bytes:
    # 24kHz × 2 s × 1 ch × 2 bytes (16-bit) = 96_000 zero bytes
    return b"\x00\x00" * 24_000 * 2


def test_write_wav_round_trip(tmp_path: Path) -> None:
    pcm = _two_seconds_of_silence()
    out = tmp_path / "out.wav"
    write_pcm16_to_wav(pcm, out)
    with wave.open(str(out)) as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 24000
        assert w.getnframes() == len(pcm) // 2
        assert w.readframes(w.getnframes()) == pcm


def test_write_wav_to_buffer() -> None:
    pcm = _two_seconds_of_silence()
    buf = io.BytesIO()
    write_pcm16_to_wav(pcm, buf, sample_rate=16000)
    blob = buf.getvalue()
    assert blob[:4] == b"RIFF"
    assert blob[8:12] == b"WAVE"
    # The sample rate field is at offset 24 (little-endian, 4 bytes)
    rate = struct.unpack("<I", blob[24:28])[0]
    assert rate == 16000


def test_write_wav_empty_raises() -> None:
    with pytest.raises(ValueError):
        write_pcm16_to_wav(b"", io.BytesIO())


def test_turn_write_wav_uses_audio_meta(tmp_path: Path) -> None:
    pcm = _two_seconds_of_silence()
    turn = Turn(audio=pcm, audio_meta={"sample_rate": 16000, "channels": 1})
    out = turn.write_wav(tmp_path / "turn.wav")
    with wave.open(str(out)) as w:
        assert w.getframerate() == 16000


def test_play_pcm16_without_extra_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate ``sounddevice`` missing and confirm we point the user at
    the optional extra instead of a bare ImportError."""
    import builtins
    real_import = builtins.__import__

    def fake_import(name: str, *args, **kw):
        if name in {"sounddevice", "numpy"}:
            raise ImportError(f"No module named '{name}'")
        return real_import(name, *args, **kw)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError, match="vocence\\[audio\\]"):
        play_pcm16(_two_seconds_of_silence())
