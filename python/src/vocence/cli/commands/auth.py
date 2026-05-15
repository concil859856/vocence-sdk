"""`vocence login` — browser device-code flow with a paste fallback.

Default flow (no flags):
    1. CLI calls POST /api/cli/device-code → gets ``user_code`` + verify URL.
    2. CLI opens the verify URL with ``user_code`` pre-filled in the browser.
    3. User signs in (if needed) and clicks "Authorize".
    4. CLI polls GET /api/cli/devices/{device_code} until status='approved',
       receiving the plaintext API key exactly once.
    5. Key is verified (account snapshot) and saved to ``~/.vocence/config.json``.

Fallback (``--paste``):
    Old manual flow — user creates a key on the website themselves and
    pastes it in. Useful if the browser can't be opened (CI, SSH session
    without ``DISPLAY``, etc.).
"""

from __future__ import annotations

import sys
import time
import urllib.parse
import webbrowser

import httpx
import typer

from ... import Vocence, errors
from ..._version import __version__
from .. import config

# Cloudflare's default WAF in front of *.vocence.ai blocks the literal
# ``Python-urllib/3.x`` user-agent. We send our SDK's canonical UA so
# the CLI flow doesn't get bounced at the edge before it reaches the
# device-code endpoint.
_UA = f"vocence-python/{__version__}"


def login(
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        "-k",
        help="Skip the browser flow and save this key directly. Implies --paste.",
    ),
    paste: bool = typer.Option(
        False,
        "--paste",
        help="Skip the browser flow and prompt for a key you'll paste in.",
    ),
    backend_url: str | None = typer.Option(
        None,
        "--backend",
        help="Override the website-backend URL (advanced; defaults to backend.vocence.ai).",
    ),
    timeout: int = typer.Option(
        300,
        "--timeout",
        help="Seconds to wait for browser approval before giving up.",
    ),
) -> None:
    """Authenticate the CLI.

    Default uses a browser-based device-code flow. Use ``--paste`` if
    you'd rather create the key on the website and paste it yourself.
    """
    if api_key:
        key = api_key.strip()
    elif paste:
        key = _prompt_paste()
    else:
        try:
            key = _device_flow(backend_url=backend_url, timeout=timeout)
        except _DeviceFlowError as e:
            typer.secho(f"Browser flow failed: {e}", fg=typer.colors.RED, err=True)
            typer.echo("Falling back to manual paste. Use --paste next time to skip the prompt.")
            key = _prompt_paste()
    _verify_and_save(key)


# --------------------------------------------------------------------- helpers


class _DeviceFlowError(RuntimeError):
    pass


def _prompt_paste() -> str:
    if sys.stdin.isatty():
        key = typer.prompt("Paste your voc_live_... API key", hide_input=True).strip()
    else:
        key = sys.stdin.read().strip()
    if not key:
        typer.secho("No key supplied.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    return key


def _default_backend_url() -> str:
    """Where the device-code endpoints live. Independent of the API
    base URL the SDK calls for ``voc_live_…``-authed routes — the CLI
    auth endpoints are on the website-backend host."""
    import os
    return (os.environ.get("VOCENCE_BACKEND_URL") or "https://backend.vocence.ai").rstrip("/")


def _device_flow(*, backend_url: str | None, timeout: int) -> str:
    base = (backend_url or _default_backend_url()).rstrip("/")
    # 1. Start the flow.
    try:
        code = _http_post_json(f"{base}/api/cli/device-code", body=b"")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise _DeviceFlowError(
                f"the backend at {base} does not implement the CLI login flow "
                "yet. Use `vocence login --paste` instead, or point at a "
                "backend that has it via VOCENCE_BACKEND_URL."
            ) from e
        raise _DeviceFlowError(f"HTTP {e.response.status_code} from {base}: {e}") from e
    except httpx.HTTPError as e:
        raise _DeviceFlowError(f"could not reach {base}: {e}") from e
    user_code: str = code["user_code"]
    device_code: str = code["device_code"]
    verify_url: str = code["verification_url"]
    interval: int = int(code.get("interval") or 3)
    expires_in: int = int(code.get("expires_in") or 600)

    # 2. Direct the user to the browser.
    full_url = f"{verify_url}?user_code={urllib.parse.quote(user_code)}"
    typer.echo(f"\nVisit this URL in a browser to authorize the CLI:\n  {full_url}")
    typer.echo(f"\nVerification code: {typer.style(user_code, bold=True, fg=typer.colors.YELLOW)}")
    typer.echo(f"This code expires in {expires_in // 60} minutes.\n")
    try:
        webbrowser.open(full_url, new=2, autoraise=True)
    except Exception:
        pass  # CI or headless — user can copy-paste

    # 3. Poll until approved / denied / expired / timeout.
    deadline = time.monotonic() + min(timeout, expires_in)
    last_status = ""
    while time.monotonic() < deadline:
        time.sleep(interval)
        try:
            r = _http_get_json(f"{base}/api/cli/devices/{urllib.parse.quote(device_code)}")
        except httpx.HTTPError as e:
            raise _DeviceFlowError(f"network error: {e}") from e
        status = r.get("status", "")
        if status != last_status:
            typer.echo(f"  → {status}")
            last_status = status
        if status == "approved":
            key = (r.get("api_key") or "").strip()
            if not key:
                raise _DeviceFlowError(
                    "server reported approved but did not return a key (was the code already consumed?)"
                )
            return key
        if status == "denied":
            raise _DeviceFlowError("you denied this CLI from the browser")
        if status == "expired":
            raise _DeviceFlowError("verification code expired before approval")
    raise _DeviceFlowError("timed out waiting for browser approval")


def _verify_and_save(key: str) -> None:
    if not key.startswith("voc_"):
        typer.secho(
            f"Warning: key doesn't start with 'voc_' — got '{key[:12]}…'. Saving anyway.",
            fg=typer.colors.YELLOW,
            err=True,
        )
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
    # Show the friendly name/email when the server gave us one — humans
    # remember "medfil / medfil@…" much more reliably than a 21-digit
    # Google sub id. Fall back to the id only if both are missing.
    who = acct.name or acct.email or acct.user_id
    typer.secho(
        f"Logged in as {who} · plan={acct.plan_code} · "
        f"credits={acct.credits:,} · key saved to {config.CONFIG_FILE}",
        fg=typer.colors.GREEN,
    )


# ----- HTTP helpers -------------------------------------------------------
#
# We use httpx (the SDK's existing HTTP dependency) instead of stdlib
# urllib so the User-Agent matches the rest of the SDK
# (``vocence-python/X.Y.Z``). Cloudflare's default WAF rules in front of
# vocence.ai hosts return 403 for the literal ``Python-urllib/3.x`` UA,
# which previously made ``vocence login`` fail at the edge before the
# request even reached our backend.


def _http_post_json(url: str, *, body: bytes) -> dict:
    headers = {"Content-Type": "application/json", "User-Agent": _UA}
    resp = httpx.post(url, content=body or b"", headers=headers, timeout=30.0)
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def _http_get_json(url: str) -> dict:
    resp = httpx.get(url, headers={"User-Agent": _UA}, timeout=30.0)
    resp.raise_for_status()
    return resp.json() if resp.content else {}
