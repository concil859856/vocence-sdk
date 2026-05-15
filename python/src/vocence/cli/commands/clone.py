"""`vocence clone <wav>` — upload + save a clip as a reusable voice."""

from __future__ import annotations

from pathlib import Path

import typer

from ._common import get_client


def clone(
    audio_path: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Reference audio clip (5-30s gives the best results).",
    ),
    name: str = typer.Option(..., "--name", "-n", help="Display name for the saved voice."),
    language: str | None = typer.Option(None, "--language", "-l", help="Language hint for transcription."),
) -> None:
    """Upload + transcribe + save a clip as a reusable voice. Prints
    the new ``voice_id`` you can then pass to `vocence speak` or to
    `client.voices.speak(...)` from Python."""
    with get_client() as client:
        saved = client.voice_clone.save(
            display_name=name,
            audio_path=audio_path,
            language=language,
        )
    voice_id = saved.get("voice_id")
    ref = saved.get("ref_script") or ""
    typer.secho(f"saved voice_id={voice_id} as '{name}'", fg=typer.colors.GREEN)
    if ref:
        short = ref if len(ref) <= 120 else ref[:117] + "…"
        typer.echo(f"  · transcribed reference: {short}")
