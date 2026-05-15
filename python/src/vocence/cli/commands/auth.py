"""`vocence login` — interactive (or piped) login.

This is the manual-paste flow: the user creates an API key at
backend.vocence.ai/account/developer (or `vocence keys create` once they
have a first key), copies it, and pastes it here. We immediately verify
by hitting ``GET /v1/account`` so the user learns about a typo right away
instead of finding out the next time they try to synthesize speech.
"""

from __future__ import annotations

import sys

import typer

from ... import Vocence, errors
from .. import config


def login(
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        "-k",
        help="API key value. If omitted, you'll be prompted (or read from stdin).",
    ),
) -> None:
    """Save an API key to ``~/.vocence/config.json`` and verify it works."""
    key = (api_key or "").strip()
    if not key:
        if sys.stdin.isatty():
            key = typer.prompt("Paste your voc_live_... API key", hide_input=True).strip()
        else:
            key = sys.stdin.read().strip()
    if not key:
        typer.secho("No key supplied.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    if not key.startswith("voc_"):
        typer.secho(
            f"Warning: key doesn't start with 'voc_' — got '{key[:12]}…'. Saving anyway.",
            fg=typer.colors.YELLOW,
            err=True,
        )

    # Verify before persisting so a bad key doesn't silently get written.
    try:
        client = Vocence(api_key=key, base_url=config.get_base_url())
        acct = client.account.get()
        client.close()
    except errors.AuthenticationError:
        typer.secho("Key rejected by the server (401).", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None
    except errors.VocenceError as e:
        typer.secho(f"Could not verify key: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None

    config.set_api_key(key)
    typer.secho(
        f"Logged in as {acct.user_id} · plan={acct.plan_code} · "
        f"credits={acct.credits:,} · key saved to {config.CONFIG_FILE}",
        fg=typer.colors.GREEN,
    )
