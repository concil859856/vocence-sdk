"""`vocence usage` — recent API request history."""

from __future__ import annotations

import typer

from ._common import get_client


def usage(
    limit: int = typer.Option(20, "--limit", "-n", min=1, max=200, help="Rows to display (max 200)."),
) -> None:
    """Print the most recent developer-API calls for this account."""
    with get_client() as client:
        rows = client.account.usage(limit=limit)
    if not rows:
        typer.echo("No recent requests.")
        return
    typer.echo(
        f"{'WHEN':<19}  {'ENDPOINT':<28}  {'STATUS':<7}  {'HTTP':>4}  "
        f"{'CR':>4}  {'MS':>6}  PROVIDER"
    )
    for r in rows:
        when = (r.created_at or "")[:19]
        ms = str(r.latency_ms) if r.latency_ms is not None else "—"
        http = str(r.http_status) if r.http_status is not None else "—"
        typer.echo(
            f"{when:<19}  {r.endpoint:<28}  {r.status:<7}  {http:>4}  "
            f"{r.credits_used:>4}  {ms:>6}  {(r.provider or '')[:32]}"
        )
