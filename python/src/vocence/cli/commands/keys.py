"""`vocence keys` — list / create / revoke developer API keys."""

from __future__ import annotations

import typer

from ._common import get_client

app = typer.Typer(no_args_is_help=True, help="Manage developer API keys.")


@app.command("list")
def list_keys() -> None:
    """List the caller's API keys (secrets are never displayed)."""
    with get_client() as client:
        items = client.account.keys.list()
    if not items:
        typer.echo("No keys.")
        return
    typer.echo(f"{'ID':<32}  {'NAME':<24}  {'PREFIX':<20}  REVOKED  CREATED")
    for k in items:
        typer.echo(
            f"{k.id:<32}  {(k.name or '')[:24]:<24}  {k.key_prefix:<20}  "
            f"{'yes' if k.revoked_at else 'no':<7}  {k.created_at or ''}"
        )


@app.command("create")
def create(
    name: str = typer.Option(..., "--name", "-n", help="Friendly label for the new key."),
) -> None:
    """Create a new API key. The plaintext is printed ONCE — copy it now."""
    with get_client() as client:
        created = client.account.keys.create(name=name)
    typer.secho(
        "Key created. Copy this plaintext NOW — it cannot be retrieved later:",
        fg=typer.colors.YELLOW,
    )
    typer.echo(created.plain_key)
    typer.echo()
    typer.echo(f"id     : {created.key.id}")
    typer.echo(f"prefix : {created.key.key_prefix}")
    typer.echo(f"tier   : {created.key.tier}")


@app.command("revoke")
def revoke(
    key_id: str = typer.Argument(..., help="ID of the key to revoke (from `vocence keys list`)."),
) -> None:
    """Revoke a key. Cannot be undone."""
    with get_client() as client:
        client.account.keys.revoke(key_id)
    typer.secho(f"Revoked {key_id}.", fg=typer.colors.GREEN)
