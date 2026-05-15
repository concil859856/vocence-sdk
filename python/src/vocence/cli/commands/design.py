"""`vocence design` — design a voice from a written description.

Wraps preview + save: generates two TTS variants, plays both (if
``vocence[audio]`` is installed), asks which to keep, persists it.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import typer

from ._common import get_client


def design(
    description: str = typer.Argument(
        ...,
        help="Plain-English description of the voice you want.",
    ),
    name: str = typer.Option(
        None,
        "--name",
        "-n",
        help="Display name for the saved voice (defaults to the first 20 chars of the description).",
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        "-o",
        help="Optional WAV path to download the variant you pick.",
    ),
    auto: str | None = typer.Option(
        None,
        "--variant",
        help="Skip the interactive prompt; pick 'original' or 'revised'.",
    ),
) -> None:
    """Generate two preview variants and save the one you like best."""
    display_name = (name or description).strip()[:40] or "designed-voice"

    with get_client() as client:
        typer.echo("generating previews…")
        preview = client.voice_design.preview(voice_description=description)
        typer.echo("\n  sample script: " + preview.sample_script)
        typer.echo(f"  variant A (original): {preview.audio_a_url}")
        typer.echo(f"  variant B (revised) : {preview.audio_b_url}")

        # Play both if we can.
        chosen = (auto or "").strip().lower()
        if chosen not in {"original", "revised"}:
            _try_play(preview.audio_a_url, label="variant A (original)")
            _try_play(preview.audio_b_url, label="variant B (revised)")
            chosen = typer.prompt("which variant?", default="revised").strip().lower()
            if chosen not in {"original", "revised"}:
                typer.secho(f"unknown variant: {chosen}", fg=typer.colors.RED, err=True)
                raise typer.Exit(code=1)

        saved = client.voice_design.save(
            preview_token=preview.preview_token,
            chosen_variant=chosen,  # type: ignore[arg-type]
            display_name=display_name,
        )
    voice_id = saved.get("voice_id")
    typer.secho(f"\nsaved voice_id={voice_id} as '{display_name}'", fg=typer.colors.GREEN)
    audio_url = saved.get("audio_url") or ""
    if out and audio_url:
        urllib.request.urlretrieve(audio_url, out)  # noqa: S310 — signed URL we just received
        typer.echo(f"  · downloaded → {out}")


def _try_play(url: str, *, label: str) -> None:
    """Best-effort: download + play the preview audio. Silent if the
    [audio] extra isn't installed or the URL fails."""
    try:
        import io

        from ..._audio import _require_audio
        sd, np = _require_audio()
        with urllib.request.urlopen(url, timeout=20) as r:  # noqa: S310 — signed URL we just received
            blob = r.read()
        # Best path: read as WAV via stdlib so we don't have to parse anything else.
        import wave
        with wave.open(io.BytesIO(blob)) as w:
            rate = w.getframerate()
            channels = w.getnchannels()
            frames = w.readframes(w.getnframes())
        arr = np.frombuffer(frames, dtype="<i2").reshape(-1, channels)
        typer.echo(f"  ▸ playing {label}…")
        sd.play(arr, samplerate=rate, blocking=True)
    except ImportError:
        typer.echo(f"  (install vocence[audio] to hear {label})")
    except Exception:
        # Don't make the whole flow fail on a playback hiccup.
        typer.echo(f"  (couldn't play {label})")
