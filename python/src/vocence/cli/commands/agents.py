"""`vocence agents` — CRUD over your Studio agents from the shell."""

from __future__ import annotations

import json

import typer

from ._common import get_client

app = typer.Typer(no_args_is_help=True, help="Manage your agents.")


@app.command("list")
def list_agents() -> None:
    """Compact id+name list of every agent on this account."""
    with get_client() as client:
        items = client.agents.list()
    if not items:
        typer.echo("No agents.")
        return
    for a in items:
        typer.echo(f"{a.id}  {a.name}")


@app.command("show")
def show(agent_id: str = typer.Argument(..., help="Agent id (from `vocence agents list`).")) -> None:
    """Print one agent's full spec (config + bound custom tools)."""
    with get_client() as client:
        a = client.agents.get(agent_id)
    typer.echo(json.dumps(a.model_dump(), indent=2))


@app.command("create")
def create(
    name: str = typer.Option(..., "--name", "-n"),
    type_: str = typer.Option("knowledge", "--type", "-t", help="'knowledge' | 'goal'"),
    voice: str | None = typer.Option(None, "--voice", help="Built-in or saved voice id."),
    language: str | None = typer.Option(None, "--language", help="Spoken language, e.g. 'English'."),
    system_prompt: str | None = typer.Option(None, "--system-prompt", "-s"),
    purpose: str | None = typer.Option(None, "--purpose"),
) -> None:
    """Create a new agent. Returns the new agent's id."""
    with get_client() as client:
        a = client.agents.create(
            name=name,
            type=type_,
            voice=voice,
            language=language,
            system_prompt=system_prompt,
            purpose=purpose,
        )
    typer.echo(a.id)


@app.command("delete")
def delete(agent_id: str = typer.Argument(..., help="Agent id to delete.")) -> None:
    """Delete an agent. Cascades to its bound tools and run history."""
    with get_client() as client:
        client.agents.delete(agent_id)
    typer.secho(f"deleted {agent_id}", fg=typer.colors.GREEN)
