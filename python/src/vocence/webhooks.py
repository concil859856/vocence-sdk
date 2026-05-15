"""Webhook signature verification for custom-tool callbacks.

When a user registers a custom tool (``POST /v1/agent-tools``) Vocence
will call the tool's ``endpoint_url`` whenever an agent's LLM picks
the tool. Vocence signs these outbound requests so the user's webhook
can confirm the request actually came from Vocence (and isn't a random
attacker who scanned the public URL).

Wire format
-----------

Two headers travel on every signed request:

    X-Vocence-Timestamp: 1731478800
    X-Vocence-Signature: v1=base64(HMAC-SHA256(secret, f"v1.{ts}.{raw_body}"))

To verify, the receiver reconstructs the signed string + recomputes the
MAC + constant-time-compares to the header. The timestamp prevents
replay (default tolerance: 5 minutes).

The shared secret is the ``auth_secret`` the user supplied when
creating the tool (``auth_type="bearer"`` or ``auth_type="header"``).
For ``auth_type="none"`` tools Vocence does NOT sign — there's nothing
to share. Document this in your tool registration UX.

Quick start
-----------

.. code-block:: python

    from fastapi import FastAPI, Request, HTTPException
    from vocence import webhooks

    app = FastAPI()
    SECRET = "your-webhook-shared-secret"  # match the value you registered

    @app.post("/api/stock")
    async def stock(request: Request):
        body = await request.body()
        if not webhooks.verify(dict(request.headers), body, SECRET):
            raise HTTPException(401, "bad signature")
        args = json.loads(body)
        ...

Or use the FastAPI helper to drop the boilerplate:

.. code-block:: python

    from vocence.webhooks import fastapi_verifier
    verify = fastapi_verifier(secret=SECRET)

    @app.post("/api/stock", dependencies=[Depends(verify)])
    async def stock(...): ...
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from collections.abc import Callable
from typing import Any

#: How far the receiver's clock can drift from Vocence's before we
#: reject a request as a replay. 5 minutes balances NTP slop against
#: stale-replay risk.
DEFAULT_TOLERANCE_SECONDS = 300

#: Header carrying the unix timestamp the signature was computed against.
HEADER_TIMESTAMP = "x-vocence-timestamp"

#: Header carrying the signature itself.
#: Format: ``v1=BASE64`` — the prefix lets us bump the scheme later.
HEADER_SIGNATURE = "x-vocence-signature"

_SIG_PREFIX = "v1="


def sign(body: bytes, secret: str, *, timestamp: int | None = None) -> dict[str, str]:
    """Compute the signature headers for a payload.

    Server-side helper — most users won't call this. We expose it so
    integration tests can fake-sign requests as Vocence would, and so
    you can verify the spec by computing a known input/output pair."""
    ts = int(timestamp if timestamp is not None else time.time())
    mac = hmac.new(
        secret.encode("utf-8"),
        f"v1.{ts}.".encode() + body,
        hashlib.sha256,
    ).digest()
    return {
        HEADER_TIMESTAMP: str(ts),
        HEADER_SIGNATURE: _SIG_PREFIX + base64.b64encode(mac).decode("ascii"),
    }


def verify(
    headers: dict[str, str],
    body: bytes | str,
    secret: str,
    *,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: int | None = None,
) -> bool:
    """Return ``True`` iff the signature header is present, fresh, and a
    correct HMAC-SHA256 of ``v1.<timestamp>.<raw_body>`` under ``secret``.

    Header lookup is case-insensitive so the function works against
    ``request.headers`` from any reasonable framework. Constant-time
    comparison protects against timing-side-channel guesses of the
    signature.
    """
    if isinstance(body, str):
        body = body.encode("utf-8")
    h = {k.lower(): v for k, v in headers.items()}
    ts_raw = h.get(HEADER_TIMESTAMP)
    sig_raw = h.get(HEADER_SIGNATURE)
    if not ts_raw or not sig_raw or not sig_raw.startswith(_SIG_PREFIX):
        return False
    try:
        ts = int(ts_raw)
    except ValueError:
        return False
    cur = int(now if now is not None else time.time())
    if abs(cur - ts) > tolerance_seconds:
        return False
    try:
        provided = base64.b64decode(sig_raw[len(_SIG_PREFIX):], validate=True)
    except Exception:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        f"v1.{ts}.".encode() + body,
        hashlib.sha256,
    ).digest()
    return hmac.compare_digest(provided, expected)


def fastapi_verifier(secret: str, *, tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS) -> Callable[[Any], Any]:
    """Return a FastAPI dependency that enforces ``verify`` on each call.

    Usage::

        verify_dep = fastapi_verifier(secret=YOUR_SECRET)

        @app.post("/api/stock", dependencies=[Depends(verify_dep)])
        async def stock(...): ...

    On signature failure the dependency raises ``HTTPException(401)``.
    On success it returns ``None`` so the route handler runs normally.
    """
    # Lazy-import FastAPI so this module is usable in scripts that don't
    # depend on the framework.
    from fastapi import HTTPException, Request

    async def _dep(request: Request) -> None:
        body = await request.body()
        if not verify(dict(request.headers), body, secret, tolerance_seconds=tolerance_seconds):
            raise HTTPException(status_code=401, detail="Invalid Vocence webhook signature.")

    return _dep


__all__ = [
    "DEFAULT_TOLERANCE_SECONDS",
    "HEADER_SIGNATURE",
    "HEADER_TIMESTAMP",
    "fastapi_verifier",
    "sign",
    "verify",
]
