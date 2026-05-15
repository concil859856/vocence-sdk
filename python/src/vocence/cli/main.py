"""`vocence` CLI entry point.

We use Typer (a thin Click wrapper) for argument parsing because it gives us
short help screens, optional arguments, and shell completion essentially for
free. Commands live in submodules under ``vocence.cli.commands``.
"""

from __future__ import annotations

import typer

from .commands import account as account_cmds
from .commands import auth as auth_cmds
from .commands import config as config_cmds
from .commands import keys as keys_cmds
from .commands import usage as usage_cmds
from .commands import voices as voices_cmds

app = typer.Typer(
    name="vocence",
    help="Vocence CLI — login, manage API keys, check your balance, and run quick TTS / STT calls.",
    add_completion=False,
    no_args_is_help=True,
)

# Top-level commands (login is at top level by convention, like `gh auth login`).
app.command("login")(auth_cmds.login)

# Sub-command groups.
app.add_typer(config_cmds.app, name="config", help="Inspect or update CLI configuration.")
app.add_typer(keys_cmds.app, name="keys", help="Manage developer API keys.")
app.add_typer(account_cmds.app, name="account", help="Show plan and credit balance.")

# Short utility commands.
app.command("voices")(voices_cmds.voices)
app.command("speak")(voices_cmds.speak)
app.command("transcribe")(voices_cmds.transcribe)
app.command("usage")(usage_cmds.usage)


if __name__ == "__main__":  # pragma: no cover
    app()
