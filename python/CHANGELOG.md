# Changelog

All notable changes to the `vocence` Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] — 2026-05-15

### Added
- **Audio download helpers** on ``TtsResponse`` / ``CloneResponse`` /
  ``AudioResponse``: ``.download() -> bytes`` and ``.write_wav(path)``.
  No more ``httpx.get(resp.audio_url).content`` boilerplate.
- **``client.tts.estimate(text, voice=...)``** — local credit-cost
  calculation; no HTTP round-trip.
- **``client.health()``** / **``client.aping()``** — quick readiness +
  auth verification, no charge.
- **``vocence.batch`` module** — ``tts_speak``, ``tts_generate``,
  ``stt_transcribe`` async helpers with ``max_concurrency`` cap and
  ``BatchError`` per-item failure wrapping (one bad row doesn't kill
  the run).
- **Per-request ``timeout=`` override** on TTS resource methods (and
  the underlying HTTP transport).
- **Voice clone from URL** — ``client.voice_clone.create(audio_url="https://…")``
  fetches the clip client-side and base64-encodes it transparently.
- **``vocence.webhooks`` module** — HMAC-SHA256 signature verification
  for custom-tool webhooks (``X-Vocence-Signature`` / ``X-Vocence-Timestamp``
  headers, replay protection, FastAPI dependency helper). Ready as soon
  as the backend ships outbound signing.

## [0.3.0] — 2026-05-15

### Added
- **Automatic retries** with exponential backoff + jitter on 429 (honors
  ``Retry-After``), transient 5xx (502/503/504), and network errors.
  GETs always retry; mutating verbs (POST/PATCH/DELETE) opt-in via
  ``Vocence(retry_mutations_on_5xx=True)``. Disable entirely with
  ``max_retries=0``.
- **``client.last_request_id``** — server-issued request id from the most
  recent HTTP call, useful for support tickets.
- **Optional ``[audio]`` extra** (``pip install vocence[audio]``) pulls
  ``sounddevice`` + ``numpy``.
- **``Turn.write_wav(path)``** — serialize a turn's audio to a proper
  WAV file (no manual PCM-to-WAV header writing).
- **``Turn.play()``** — play the assistant's reply through the default
  output device.
- **Live mic↔agent chat** — ``client.agents.live_chat(agent_id)`` opens
  a push-to-talk WS session, ships base64-encoded audio, plays the reply
  in real time as frames arrive.
- **CLI: ``vocence chat <agent>``** — text REPL with the conversation
  helper (plays audio if ``[audio]`` is installed).
- **CLI: ``vocence voice <agent>``** — push-to-talk mic REPL.
- **CLI: ``vocence agents list/show/create/delete``** — agent CRUD.
- **CLI: ``vocence design "warm female narrator"``** — preview + interactive
  variant picker + save.
- **CLI: ``vocence clone <wav> --name "..."``** — one-shot upload + save.

## [0.2.0] — 2026-05-15

### Added
- **Sync WebSocket session** — ``client.agents.session(agent_id)`` on the
  sync ``Vocence`` client now returns a blocking ``SyncAgentSession``
  context manager, so non-async scripts can drive voice agents without
  touching asyncio.
- **High-level conversation helper** — ``client.agents.conversation(agent_id)``
  on ``AsyncVocence`` wraps the raw event stream with batched ``say()`` /
  ``send_voice()`` turn semantics. Each call returns a ``Turn`` carrying
  the assistant's full text, all audio bytes concatenated, audio metadata,
  and any tool calls the LLM made.
- **``client.account.usage(limit=N)``** + **``vocence usage``** CLI command —
  recent API request log (timestamp, endpoint, http status, credits, latency,
  error info).
- **Browser device-code login** — ``vocence login`` now opens
  ``backend.vocence.ai/cli/authorize`` in a browser, polls for approval,
  and stores the freshly-minted key. Old paste flow is still available
  via ``--paste`` or ``--api-key voc_live_…``.

### Fixed
- Sync WS wrapper no longer races on shutdown: exceptions raised inside the
  background event loop are now always observable from the consumer thread.

## [0.1.0] — 2026-05-15

### Added
- Initial release.
- Sync `Vocence` client + async `AsyncVocence` client.
- Resources covering every REST endpoint of the Vocence Developer API:
  - `tts.generate`, `tts.speak`
  - `stt.transcribe`
  - `voice_clone.create`, `voice_clone.save`
  - `voice_design.preview`, `voice_design.save`
  - `voices.list`, `voices.builtin`, `voices.get`, `voices.delete`, `voices.speak`
  - `agents.list`, `agents.get`, `agents.create`, `agents.update`, `agents.delete`
  - `agents.tools.list`, `agents.tools.bind`, `agents.tools.unbind`
  - `agent_tools.list`, `agent_tools.get`, `agent_tools.create`,
    `agent_tools.update`, `agent_tools.delete`
  - `account.get`, `account.keys.list`, `account.keys.create`, `account.keys.revoke`
- Async WebSocket session helper for `/v1/agents/{id}/session` that yields
  typed events (`ready`, `token`, `audio_meta`, binary audio, `turn_end`, …).
- Pydantic v2 response models in `vocence.types`.
- Exception hierarchy: `VocenceError`, `AuthenticationError`, `RateLimitError`,
  `InsufficientCreditsError`, `BadRequestError`, `NotFoundError`, `UpstreamError`.
- `vocence` CLI: `login`, `config`, `account`, `keys`, `voices`, `speak`,
  `transcribe`.
