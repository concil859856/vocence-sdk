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
