# Changelog

All notable changes to the `vocence` Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.2] - 2026-06-19

### Fixed

- **`AsyncVocence().tts.estimate(...)` is now awaitable.** The
  inherited `staticmethod` made the async-client call return a
  bare dataclass while the IDE / type checker said it was a
  coroutine — `await` raised `TypeError: object Estimate can't be
  used in 'await' expression`. The async client now exposes its
  own `async def estimate(...)` that wraps the same pure-local
  arithmetic, so `await client.tts.estimate(...)` works without
  surprise. The sync `Vocence().tts.estimate(...)` stays sync.
- **`voice_design.preview()` response model.** Schema rewritten
  to match what `/v1/voice/design/preview` actually returns. Old
  fields removed (`sample_script`, `audio_a_url`, `audio_b_url`,
  `expires_at`, `credits`); new fields are `audio_url` (single
  variant — the API surfaces only the deterministic "original"
  variant by design), plus `credits_used` and `credits_remaining`.
  Existing code that read those old fields will need to switch to
  `audio_url`. The two-variant A/B preview remains a website-UI
  feature only.

## [0.7.1] - 2026-06-19

### Added

- **Call history retrieval.** New helper
  `client.agents.calls(agent_id)` with methods `list()`,
  `transcript(session_id)`, `recording(session_id, *, download=False)`,
  and `delete_recording(session_id)`. Mirrors the dashboard's
  per-agent call view: list recent calls (range/limit-paged),
  fetch a turn-by-turn transcript with `at_ms` offsets relative to
  call start, or pull a 1-hour presigned R2 URL for the stereo WAV
  (left=user mic post-denoise, right=agent TTS, both 16 kHz
  s16le, one shared timeline). Recordings only exist when the
  agent's `config.record_enabled = true` for the call. Both
  sync (`Vocence`) and async (`AsyncVocence`) flavors are exposed.
- **`AgentConfig` voice-pipeline knobs** now typed on the SDK:
  `denoise_enabled`, `turn_decider` (`"ultravad" | "fusion"`),
  `ultravad_threshold` (default 0.50), `min_delay_ms`,
  `record_enabled`. Pass any of them to `agents.create(...)` or
  `agents.update(agent_id, ...)`. Existing code that only set the
  legacy fields is unchanged.

### Changed

- **`agents.create()` / `AsyncAgentsResource.create()`** now accept
  `first_message`, `denoise_enabled`, `turn_decider`,
  `ultravad_threshold`, `min_delay_ms`, `record_enabled` as
  explicit keyword arguments. None of these are required; the
  server fills in sensible defaults when omitted.
- **`AgentConfig.ultravad_threshold` default** dropped from `0.55`
  → `0.50` to match the server's new default. Slightly snappier
  turn-taking baseline.
- **README cross-reference to `vocence-plugins`** — sibling package
  for developers running their own real-time voice-agent pipeline
  who want Vocence voices + recognition as drop-in components.
  Same `voc_live_…` key, no functional overlap with this SDK; see
  the "Building your own pipeline?" section.

### Notes

- The server now sends a new WebSocket message,
  `{"type": "flush_player"}`, when a `stream_start` / `voice` /
  `text` turn opens while previous-reply audio is still in the
  client's playback queue. The current SDK's `AgentSession` /
  `SyncAgentSession` don't intercept it (audio playback is on
  the caller's side); custom WebSocket clients should handle it
  as "flush my local audio buffer, leave the active stream
  session alone." See API docs §Voice Agent WebSocket → Barge-in
  protocol for the full semantic.

## [0.7.0] — 2026-06-11

### Added

- **`AgentSession.notify_audio_started()`** /
  **`notify_audio_settled()`** — optional protocol hooks the client
  can fire to tell the server when the agent's audio is actually
  reaching the user's speakers vs has gone silent again. The server
  uses these signals to latch / release a mic-mute gate, dropping
  echo PCM frames before they reach STT. Pairs with
  `start_stream()` / `send_pcm()`; pure `send_text` / `send_voice`
  clients can ignore entirely. Both methods are also exposed on
  `SyncAgentSession` as blocking calls.
- README section "Optional: audio-lifecycle notifications (tighter
  barge-in)" with a concrete code example showing where to fire
  each method in a streaming-PCM client loop.

### Notes

- Skipping these notifications is safe — the server has a ~6 s
  safety auto-release on the mic gate, so barge-in still works
  without client participation. The protocol additions just make
  interruption feel noticeably crisper for clients that opt in.
- Backwards compatible. No existing API changed; this is purely
  additive.

## [0.6.1] — 2026-06-01

### Added

- **`SessionEndedError`** — typed exception raised when the server
  closes an agent WebSocket session before the caller asks it to.
  Carries `reason` (`"max_duration"` / `"idle_timeout"` /
  `"agent_paused"`) and the raw `code`, so apps can distinguish
  "session naturally timed out" from "agent was paused" without
  parsing close-code numbers.
- **Client-side URL scheme guard** on `knowledge.ingest_url` /
  `knowledge.ingest_sitemap`. Non-HTTP schemes (`file://`, `ftp://`,
  …) and obvious private hosts (`localhost`, `127.x`,
  `169.254.169.254`) now raise `ValueError` *before* the HTTP round-
  trip instead of returning a server-side HTTP 400. Server-side
  validation (with DNS resolution) is unchanged and remains the
  authoritative check.

### Improved

- Close-code mapping in `AgentSession` now covers
  `4402 → InsufficientCreditsError`, `4429 → RateLimitError`,
  `{4408, 4410, 4423} → SessionEndedError`, `{4500, 4502, 4503} →
  UpstreamError` in addition to the existing `4401 / 4404` mappings.
  Previously these codes ended iteration silently — callers had no
  way to distinguish a timeout from a payment failure.

## [0.6.0] — 2026-06-01

### Added

- **`client.feedback`** — record thumbs-up / thumbs-down on a
  generation so you can collect quality signal on the AI outputs
  you ship to your own users.
  ```python
  client.feedback.submit(
      entry_type="tts",          # or stt / voice_clone / voice_design /
                                 # music / noise_remover / agent_call /
                                 # agent_message
      entry_id="job_abc123",
      rating=-1,                 # -1 thumb-down, 1 thumb-up, 0 = un-vote
      comment="Voice sounded robotic on long sentences",
  )
  state = client.feedback.get(entry_type="tts", entry_id="job_abc123")
  ```
  Async sibling via ``AsyncVocence.feedback``.

- **Agent discovery endpoints** on ``client.agents``:
  ``templates()`` / ``template(id)`` (starter gallery + full body),
  ``models()`` (LLM picker), ``builtin_tools()`` (web-search, weather,
  datetime, …). Use these to build your own agent-builder UI without
  hard-coding the available options.

- **LLM-powered agent authoring** on ``client.agents``:
  ``draft(description, type_hint=None, existing=None)`` for a one-shot
  spec generator, and ``architect_chat(message, history=[], existing=None)``
  for the iterative back-and-forth flow the website's Architect Drawer
  uses. ``architect_chat`` returns ``{reply, proposed_changes}`` —
  show "Apply" only when ``proposed_changes`` is non-None.

- **Goal-agent runs** at ``client.agents.runs(agent_id)`` —
  ``list()`` / ``start()`` / ``get(run_id)`` / ``cancel(run_id)``.
  Only meaningful for agents with ``type == 'goal'``. ``cancel`` is
  idempotent; ``list`` returns ``[]`` for knowledge-style agents so
  you can treat both uniformly.

## [0.5.0] — 2026-06-01

### Added

- **Streaming voice on `AgentSession`**. Pair with the dashboard /
  developer-api `capabilities.voice_stream` flag to push live PCM
  frames instead of one-shot WAV uploads:
  ```python
  async with client.agents.session(agent_id) as sess:
      caps = await sess.wait_ready()
      if caps.get("voice_stream"):
          await sess.start_stream()
          for frame in pcm_frames():   # 16 kHz mono s16le
              await sess.send_pcm(frame)
          await sess.commit_stream()
      else:
          await sess.send_voice(wav_b64)
  ```
  New methods: ``start_stream``, ``send_pcm``, ``commit_stream``,
  ``wait_ready``. ``session.capabilities`` and ``session.session_id``
  are populated from the server's ``ready`` event whether you call
  ``wait_ready`` or iterate the session directly.

- **`client.agents.knowledge(agent_id)`** — per-agent RAG knowledge
  ingestion mirroring `/v1/agents/{id}/knowledge/*`:
  ``ingest_text``, ``ingest_markdown``, ``ingest_url``,
  ``ingest_sitemap``, ``ingest_pdf`` (path / bytes / file-like),
  ``sources``, ``delete_source``, ``job(job_id)`` for polling.
  Async sibling available at ``await client.agents.knowledge(...)``.

- **`client.agents.embed_tokens(agent_id)`** — mint, list, and revoke
  embed tokens for the embeddable ``<vocence-agent>`` widget. The
  plaintext is returned ONCE on create; subsequent listings return
  metadata only.

### Behaviour
- Inherits the dashboard's recent voice-chat hardening transparently
  via the WS relay: forward-frames wait-for-final, stray-commit
  no-op, Logos default greeting on sessionless calls. No SDK
  changes required.

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
