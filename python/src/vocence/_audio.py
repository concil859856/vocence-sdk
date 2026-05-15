"""Audio helpers — WAV serialization (stdlib only) + optional playback.

The agent WebSocket streams PCM16LE mono frames at the sample rate
announced in the preceding ``audio_meta`` event. Most callers want one
of two things: dump the bytes to a ``.wav`` file, or play them back
through the speakers. Both are covered here.

Playback uses the optional ``sounddevice`` package, which is itself a
thin wrapper around PortAudio. Install with ``pip install vocence[audio]``.
If the package isn't installed, :func:`play_pcm16` raises a friendly
``ImportError`` pointing at the extra — the rest of the SDK keeps
working without it.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import IO

_DEFAULT_SAMPLE_RATE = 24000
_DEFAULT_CHANNELS = 1
_DEFAULT_BITS = 16


def write_pcm16_to_wav(
    pcm: bytes,
    out: str | Path | IO[bytes],
    *,
    sample_rate: int = _DEFAULT_SAMPLE_RATE,
    channels: int = _DEFAULT_CHANNELS,
) -> None:
    """Serialize raw little-endian PCM16 mono/stereo to a WAV file.

    Why the in-house writer instead of ``wave`` from the stdlib? The
    stdlib accepts a path or a file-like object, and we want both, but
    its ``setparams()`` API is fiddly. A direct RIFF/WAVE write is ~30
    lines and gives us a single code path.
    """
    if not pcm:
        raise ValueError("PCM payload is empty.")
    bits = _DEFAULT_BITS
    byte_rate = sample_rate * channels * (bits // 8)
    block_align = channels * (bits // 8)
    data_size = len(pcm)
    riff_size = 4 + (8 + 16) + (8 + data_size)
    header = b"RIFF" + struct.pack("<I", riff_size) + b"WAVE"
    fmt = (
        b"fmt " + struct.pack("<I", 16)  # PCM fmt chunk size
        + struct.pack("<HHIIHH", 1, channels, sample_rate, byte_rate, block_align, bits)
    )
    data = b"data" + struct.pack("<I", data_size) + pcm
    blob = header + fmt + data

    if hasattr(out, "write"):
        out.write(blob)  # type: ignore[union-attr]
    else:
        Path(out).write_bytes(blob)  # type: ignore[arg-type]


def play_pcm16(
    pcm: bytes,
    *,
    sample_rate: int = _DEFAULT_SAMPLE_RATE,
    channels: int = _DEFAULT_CHANNELS,
    blocking: bool = True,
) -> None:
    """Play raw little-endian PCM16 through the default audio device.

    Requires the optional ``sounddevice`` package — install with
    ``pip install vocence[audio]``.
    """
    sd, np = _require_audio()
    # Interpret raw bytes as a (samples, channels) int16 array.
    arr = np.frombuffer(pcm, dtype="<i2").reshape(-1, channels)
    sd.play(arr, samplerate=sample_rate, blocking=blocking)


def _require_audio() -> tuple:
    """Lazy-load the optional audio dependencies; raise a helpful error
    if they aren't installed."""
    try:
        import numpy as np  # noqa: I001
        import sounddevice as sd  # noqa: I001
    except ImportError as e:
        raise ImportError(
            "vocence[audio] is not installed. Run `pip install \"vocence[audio]\"` to "
            "enable Turn.play() / AudioFrame.play() and the live-chat helpers."
        ) from e
    return sd, np
