"""`vocence config` — view / unset configuration values."""

from __future__ import annotations

import typer

from .. import config as cfg

app = typer.Typer(no_args_is_help=True, help="Inspect or update CLI configuration.")


@app.command("show")
def show() -> None:
    """Print the current saved configuration (key is masked)."""
    key = cfg.get_api_key()
    base = cfg.get_base_url() or "(default: https://api.vocence.ai)"
    typer.echo(f"config file : {cfg.CONFIG_FILE}")
    typer.echo(f"api_key     : {cfg.mask(key) if key else '(not set)'}")
    typer.echo(f"base_url    : {base}")


@app.command("logout")
def logout() -> None:
    """Remove the saved API key from the config file."""
    data = cfg.load()
    if "api_key" in data:
        data.pop("api_key")
        cfg.save(data)
    typer.secho("Logged out.", fg=typer.colors.GREEN)


@app.command("set-base-url")
def set_base_url(url: str = typer.Argument(..., help="Override the API base URL (e.g. for staging).")) -> None:
    """Pin the CLI to a non-default API host. Pass `default` to clear it."""
    if url.lower() in {"default", "reset", ""}:
        cfg.set_base_url(None)
        typer.echo("base_url reset to default.")
    else:
        cfg.set_base_url(url)
        typer.echo(f"base_url set to {url}")


@app.command("set-keyring")
def set_keyring(state: str = typer.Argument(..., help="'on' or 'off'.")) -> None:
    """Toggle OS-keyring storage for the API key.

    Requires ``pip install vocence[keyring]``. When ``on``, the key is
    moved from ``~/.vocence/config.json`` into the platform keychain
    on the next ``vocence login`` (or call ``vocence login --paste``
    again to move it now). When ``off``, the key falls back to the
    config file."""
    s = state.strip().lower()
    if s not in {"on", "off"}:
        typer.secho(f"unknown state: {state!r} (expected 'on' or 'off')", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    if s == "on":
        if cfg._keyring_module() is None:
            typer.secho(
                "keyring not installed. Run `pip install \"vocence[keyring]\"` first.",
                fg=typer.colors.RED, err=True,
            )
            raise typer.Exit(code=1)
        cfg.set_keyring_enabled(True)
        typer.secho(
            "keyring storage enabled. Run `vocence login` again to move the existing key into the keychain.",
            fg=typer.colors.GREEN,
        )
    else:
        cfg.set_keyring_enabled(False)
        cfg.clear_keyring_entry()
        typer.echo("keyring storage disabled.")
