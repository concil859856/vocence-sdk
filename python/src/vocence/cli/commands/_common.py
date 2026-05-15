"""Helpers shared by CLI subcommands."""

from __future__ import annotations

import typer

from ... import Vocence
from .. import config


def get_client() -> Vocence:
    """Build a Vocence client from saved config (or env), exiting cleanly
    with a friendly error if no key is configured."""
    key = config.get_api_key()
    if not key:
        typer.secho(
            "No API key configured. Run `vocence login` or set VOCENCE_API_KEY.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    return Vocence(api_key=key, base_url=config.get_base_url())
