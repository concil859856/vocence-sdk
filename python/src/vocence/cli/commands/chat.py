"""`vocence chat <agent>` and `vocence voice <agent>` — interactive REPLs."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from ... import AsyncVocence
from ._common import get_client


def chat(
    agent_id: str = typer.Argument(..., help="Agent id (see `vocence agents list`)."),
    audio_out: Path | None = typer.Option(
        None,
        "--audio-out",
        help="Optional directory to write each reply's WAV file into.",
    ),
) -> None:
    """Text REPL: type a message, hear / read the agent's reply.

    Synthesized audio is played back if ``vocence[audio]`` is installed;
    otherwise just the text is printed. Press Ctrl-D / Ctrl-C to exit.
    """
    with get_client() as client:
        base_url = client._base_url
        api_key = client._http._api_key

    async def loop() -> None:
        async with AsyncVocence(api_key=api_key, base_url=base_url) as ac:
            async with ac.agents.conversation(agent_id) as conv:
                typer.secho(f"connected to {agent_id}. type a message, blank line to quit.", fg=typer.colors.GREEN)
                turn_n = 0
                while True:
                    try:
                        line = input("you > ").strip()
                    except (EOFError, KeyboardInterrupt):
                        typer.echo()
                        break
                    if not line:
                        break
                    turn = await conv.say(line)
                    typer.echo(f"agent > {turn.text}")
                    turn_n += 1
                    if audio_out is not None and turn.audio:
                        audio_out.mkdir(parents=True, exist_ok=True)
                        path = audio_out / f"turn_{turn_n:03d}.wav"
                        turn.write_wav(path)
                        typer.echo(f"  · saved {path}")
                    elif turn.audio:
                        try:
                            turn.play(blocking=True)
                        except ImportError:
                            # No audio extra installed — that's fine,
                            # text-only mode is still usable.
                            pass

    asyncio.run(loop())


def voice(
    agent_id: str = typer.Argument(..., help="Agent id (see `vocence agents list`)."),
) -> None:
    """Mic REPL: hold a push-to-talk turn with the agent.

    Requires ``pip install vocence[audio]``. Each turn:

      1. Press Enter — recording starts.
      2. Speak.
      3. Press Enter — recording stops, clip is sent, reply plays back.

    Press Ctrl-C to leave the conversation.
    """
    with get_client() as client:
        base_url = client._base_url
        api_key = client._http._api_key

    async def loop() -> None:
        async with AsyncVocence(api_key=api_key, base_url=base_url) as ac:
            try:
                async with ac.agents.live_chat(agent_id) as live:
                    typer.secho(
                        f"connected to {agent_id}. enter to start/stop recording, ctrl-c to quit.",
                        fg=typer.colors.GREEN,
                    )
                    while True:
                        try:
                            input("\npress enter to start speaking…")
                        except (EOFError, KeyboardInterrupt):
                            typer.echo()
                            return
                        live.record()
                        try:
                            input("recording — press enter to stop…")
                        except (EOFError, KeyboardInterrupt):
                            typer.echo()
                            return
                        turn = await live.stop_and_send()
                        typer.echo(f"you   > {turn['transcript']}")
                        typer.echo(f"agent > {turn['text']}")
            except ImportError as e:
                typer.secho(f"{e}", fg=typer.colors.RED, err=True)
                raise typer.Exit(code=1) from e

    asyncio.run(loop())
