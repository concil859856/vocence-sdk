# Vocence Python SDK

[![PyPI](https://img.shields.io/pypi/v/vocence.svg)](https://pypi.org/project/vocence/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](../LICENSE)

Official Python client for the [Vocence](https://vocence.ai) Developer API.

```bash
pip install vocence
```

## Quickstart

```python
from vocence import Vocence

client = Vocence(api_key="voc_live_...")

# 1. Browse the catalog of pre-defined speakers
for v in client.voices.builtin():
    print(v.id, v.name, "—", v.description)

# 2. Synthesize text in one of them
audio = client.tts.speak(text="Hello from Vocence!", voice="design-aria")
print(audio.audio_url)

# 3. Transcribe an audio clip
text = client.stt.transcribe(audio_path="clip.wav", language="English").text
print(text)
```

Async usage mirrors the sync API exactly:

```python
import asyncio
from vocence import AsyncVocence

async def main() -> None:
    async with AsyncVocence(api_key="voc_live_...") as client:
        audio = await client.tts.speak(text="Hello", voice="design-aria")
        print(audio.audio_url)

asyncio.run(main())
```

## Voice agents over WebSocket

```python
import asyncio
from vocence import AsyncVocence

async def main() -> None:
    async with AsyncVocence(api_key="voc_live_...") as client:
        async with client.agents.session("agent-id") as session:
            await session.send_text("What's the weather in Tokyo?")
            async for event in session:
                print(event)
                if event.type == "turn_end":
                    break

asyncio.run(main())
```

The session yields typed events: `ready`, `transcript`, `token`,
`tool_call_started`, `tool_call_completed`, `audio_meta`, `audio` (binary PCM16),
`audio_end`, `turn_end`, `error`.

## CLI

```bash
$ vocence login                          # paste your voc_live_... key once
$ vocence account                        # show plan, credits remaining, key count
$ vocence keys list
$ vocence keys create --name "laptop"
$ vocence voices                         # list built-in speakers
$ vocence speak "Hello" --voice design-aria -o out.wav
$ vocence transcribe clip.wav --language English
```

Config is written to `~/.vocence/config.json`. Override the key with the
`VOCENCE_API_KEY` environment variable on any command.

## Errors

```python
from vocence import Vocence, errors

client = Vocence(api_key="voc_live_invalid")
try:
    client.tts.speak(text="x", voice="design-aria")
except errors.AuthenticationError as e:
    print("bad key:", e)
except errors.InsufficientCreditsError as e:
    print("top up:", e)
except errors.RateLimitError as e:
    print("slow down, retry after:", e.retry_after)
```

## API parity

The SDK covers 100% of the public REST + WS surface documented at
[vocence.ai/docs/api](https://vocence.ai/docs/api). See [CHANGELOG.md](CHANGELOG.md)
for what shipped in each release.

## License

Apache 2.0 — see the repo-root [LICENSE](../LICENSE).
