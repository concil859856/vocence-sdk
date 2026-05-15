"""`vocence voices`, `vocence speak`, `vocence transcribe` — quick utility
commands that exercise the most-used endpoints from the shell.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import typer

from ._common import get_client


def voices() -> None:
    """List the pre-defined sample voices the API ships."""
    with get_client() as client:
        items = client.voices.builtin()
    typer.echo(f"{'ID':<32}  {'NAME':<22}  DESCRIPTION")
    for v in items:
        typer.echo(f"{v.id:<32}  {v.name:<22}  {v.description}")


def speak(
    text: str = typer.Argument(..., help="Text to synthesize (≤ 500 chars)."),
    voice: str = typer.Option(
        "design-aria",
        "--voice",
        "-v",
        help="Built-in voice id (see `vocence voices`).",
    ),
    out: Path = typer.Option(
        Path("out.wav"),
        "--out",
        "-o",
        help="Where to save the WAV. Use `-` to print just the URL.",
    ),
) -> None:
    """Synthesize text in a built-in voice; save the WAV to disk."""
    with get_client() as client:
        result = client.tts.speak(text=text, voice=voice)
    typer.echo(result.audio_url)
    if str(out) == "-":
        return
    try:
        urllib.request.urlretrieve(result.audio_url, out)  # noqa: S310 — explicit, signed URL
    except Exception as e:
        typer.secho(f"Could not download to {out}: {e}", fg=typer.colors.YELLOW, err=True)
        return
    typer.secho(f"Saved {out}", fg=typer.colors.GREEN)


def transcribe(
    audio_path: Path = typer.Argument(..., exists=True, readable=True, help="Audio file to transcribe."),
    language: str | None = typer.Option(None, "--language", "-l", help="Language hint, e.g. English."),
) -> None:
    """Transcribe an audio file and print the text."""
    with get_client() as client:
        result = client.stt.transcribe(audio_path=audio_path, language=language)
    typer.echo(result.text)
