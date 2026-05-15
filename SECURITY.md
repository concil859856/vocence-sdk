# Security policy

## Reporting a vulnerability

Email **space@vocence.ai** with the details. Please **do not** open a
public GitHub issue for sensitive reports. We acknowledge within 2
business days and aim to ship a fix within 14 days for medium / high
severity.

PGP key, bounty program (when available), and credited researchers: TBD.

## Supported versions

We currently maintain only the latest `0.x` release line. Once 1.0
ships, we'll support the previous major in parallel for 6 months.

## Threat model

The SDK is a thin client over a public REST + WebSocket API.
Authentication is a bearer token of the form `voc_live_…` ("API key").

### Confidentiality of the API key — the central concern

The key grants full account access — TTS / STT / clone calls cost money
(credits) and the key-management endpoints let the holder mint new
keys. Treat it like a password.

Channels we control vs. channels the user controls:

| Channel | Owner | Risk mitigation |
|---|---|---|
| TLS over the wire | SDK | All requests go through `httpx`/`websockets` with default cert verification enabled. The SDK does **not** disable TLS verification, ever. |
| Bearer header value | SDK | Sent only to the configured `base_url` (default `api.vocence.ai`); never reflected back, never logged. `repr(client)` masks it. |
| In-memory lifetime | SDK | The key lives in the client object's `_api_key` attribute and in `httpx`'s default headers dict for the lifetime of the client. Use `client.close()` / `async with` to drop it ASAP. |
| `~/.vocence/config.json` | CLI | File mode `0600`, directory mode `0700`. CLI refuses to read the file if it's group- or world-readable. |
| OS keyring | CLI (optional) | `pip install vocence[keyring]` + `vocence config set-keyring on` moves the key to the platform keychain (macOS Keychain, Windows Credential Locker, freedesktop Secret Service). Recommended on shared workstations. |
| `VOCENCE_API_KEY` env var | User | Convenient for servers / CI. **Note**: visible to other processes via `/proc/<pid>/environ` on Linux, leaks into Docker image layers if set via `ENV`, and persists in shell history. Use environment-injection (k8s Secret, Docker Compose `env_file`, etc.) instead of inline. |
| `--api-key voc_live_…` on the command line | User | **Discouraged.** Appears in `ps`, in shell history, in your terminal scrollback, in process accounting logs. Prefer the env var or `vocence login`. |
| Logs / stack traces | SDK | `Vocence.__repr__` and the HTTP transport `__repr__` print the key in `voc_live_XXXX…XXXX` form so it never reaches log aggregators in full. |

### CLI device-code flow

`vocence login` uses an RFC 8628-style flow:

1. CLI POSTs to `/api/cli/device-code` and gets a 128-bit `device_code`
   plus a short `user_code` shown to the user.
2. CLI opens the website's `/cli/authorize?user_code=…` and polls
   `/api/cli/devices/{device_code}` every few seconds.
3. The user, signed in on the website, confirms the displayed
   `user_code` matches their terminal and clicks **Authorize**.
4. The website backend mints a fresh API key, stores it against the
   `device_code` row, and the CLI's next poll receives the plaintext
   exactly once. The row is marked `consumed` so the key can never be
   retrieved a second time.

Threat-by-threat:

- **Attacker steals `user_code` from over a victim's shoulder.** Useless
  — approval requires the victim's session JWT, so the attacker can't
  POST `/api/cli/approve` even with the right code.
- **Attacker phishes the victim onto `/cli/authorize?user_code=ATTACKER`**
  and the victim clicks Authorize. The approval page now shows an
  explicit security warning explaining that approval mints a new
  full-access key. We will not bypass this warning in v0 — if you have
  ideas for stronger out-of-band verification (e.g. push notification
  to a logged-in mobile session), please email space@vocence.ai.
- **Attacker spams `/api/cli/device-code` to DoS the user_code namespace.**
  Per-IP rate limit (10 codes / minute) caps the abuse.
- **Attacker intercepts the `device_code` on the wire.** Only feasible
  with a TLS MITM. We mandate HTTPS on the production endpoint via
  HSTS and the SDK's default verification posture; non-HTTPS hosts
  require the user to set `VOCENCE_BACKEND_URL` explicitly.

### What the SDK does NOT do

- It does **not** encrypt request bodies beyond TLS. Don't put secrets
  in the `text` you synthesize.
- It does **not** sign outgoing requests (HMAC, mTLS, etc.). Bearer
  auth + TLS is the documented surface.
- It does **not** validate webhook payloads from your custom tools.
  HMAC verification for those is planned for v0.4 (server-side signing
  is the prerequisite). Until then, treat custom-tool callbacks like
  any untrusted HTTP traffic on your side.
- It does **not** sandbox tool execution. Built-in tools (web_search,
  weather, time, wikipedia, fetch_url) run on the Vocence backend; your
  custom tools run wherever your webhook URL points.

### Reporting incidents

If you suspect a key has been leaked:

1. Run `vocence keys list` to find it.
2. Run `vocence keys revoke <id>` immediately.
3. `vocence keys create --name "rotated"` to issue a replacement.
4. Email space@vocence.ai with the date/time + how it leaked so we
   can correlate with our access logs.

Revocation is immediate; the revoked key returns HTTP 403 on the next
call.
