"""`vocence account` — credit balance + plan status."""

from __future__ import annotations

import typer

from ._common import get_client

app = typer.Typer(invoke_without_command=True, help="Show plan and credit balance.")


@app.callback(invoke_without_command=True)
def default(ctx: typer.Context) -> None:
    """Running ``vocence account`` with no subcommand prints the snapshot."""
    if ctx.invoked_subcommand:
        return
    _print_account()


@app.command("balance")
def balance() -> None:
    """Print just the credit balance (machine-friendly: one integer)."""
    with get_client() as client:
        acct = client.account.get()
    typer.echo(acct.credits)


def _print_account() -> None:
    with get_client() as client:
        acct = client.account.get()
    typer.echo(f"user        : {acct.user_id}{(' · ' + acct.email) if acct.email else ''}")
    typer.echo(f"plan        : {acct.plan_code} ({acct.plan_status})")
    typer.echo(f"credits     : {acct.credits:,}")
    typer.echo(f"api keys    : {acct.api_keys_count}")
