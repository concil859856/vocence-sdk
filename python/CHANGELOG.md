# Changelog

All notable changes to the `vocence` Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
