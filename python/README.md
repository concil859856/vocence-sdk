# Vocence Python SDK

[![PyPI](https://img.shields.io/pypi/v/vocence.svg)](https://pypi.org/project/vocence/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](../LICENSE)

Official Python client for the [Vocence](https://vocence.ai) Developer API.

```bash
pip install vocence              # REST + WebSocket
pip install "vocence[audio]"     # adds Turn.play() and the mic ↔ agent live-chat helper
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

For one-shot turns (no streaming), use the higher-level conversation API:

```python
async with client.agents.conversation("agent-id") as conv:
    turn = await conv.say("What's the weather in Tokyo?")
    print(turn.text)                 # "It's 19 degrees..."
    open("reply.pcm", "wb").write(turn.audio)
    print(turn.audio_meta)            # {'sample_rate': 24000, 'frame_ms': 40, ...}
```

The sync `Vocence` client exposes `client.agents.session(agent_id)` as a
blocking context manager — events are iterated with a normal `for` loop:

```python
with Vocence(api_key="voc_live_...").agents.session("agent-id") as sess:
    sess.send_text("hi")
    for event in sess:
        if event.type == "turn_end":
            break
```

### Optional: audio-lifecycle notifications (tighter barge-in)

When you're streaming user PCM back to the server (live mic input)
AND playing the agent's reply through a speaker, you can tell the
server exactly when the speakers go active vs. silent. The server
uses these signals to drop echo PCM frames before they reach STT,
which makes barge-in and interruption handling noticeably crisper.

```python
async with client.agents.session("agent-id") as sess:
    await sess.start_stream()
    async for event in sess:
        if event.type == "audio" and not playback_started:
            playback_started = True
            await sess.notify_audio_started()      # speakers went hot
            play(event.data)
        elif event.type == "audio":
            play(event.data)
        elif event.type == "turn_end":
            await wait_for_speaker_drain()
            await sess.notify_audio_settled()      # speakers silent again
            break
```

Both methods are optional. If you skip them (or one gets lost
mid-flight), the server falls back to a 6 second safety auto-release
on the mic gate — barge-in still works, it just feels a bit looser.

Same contract on the sync `Vocence` client: `sess.notify_audio_started()`
and `sess.notify_audio_settled()` are blocking calls.

## Building your own pipeline? See `vocence-plugins`

This SDK talks to a Vocence-hosted voice agent — the agent owns its
STT, LLM, TTS, knowledge base, tool dispatch, and call history. If
you instead run your own real-time voice-agent pipeline and just
want Vocence voices + recognition as components,
[`vocence-plugins`](https://pypi.org/project/vocence-plugins/) ships
drop-in `VocenceTTS` and `VocenceSTT` classes that conform to the
standard streaming TTS / STT abstract interfaces.

| Use case | Use |
|---|---|
| Talk to a Vocence-hosted voice agent | `vocence` (this package) |
| Build your own agent pipeline with Vocence voices + recognition | [`vocence-plugins`](https://pypi.org/project/vocence-plugins/) |

Same `voc_live_…` key for both. They don't overlap.

```bash
pip install vocence-plugins
```

```python
from vocence_plugins import VocenceTTS, VocenceSTT

tts = VocenceTTS(voice="design-aria", language="English")
stt = VocenceSTT(language="English")

# In your pipeline loop:
async for frame in capture_mic_at_16k_mono_pcm16le():
    await stt.process_audio(frame)        # mic in → transcripts via callback

await tts.synthesize("Hello from your own pipeline!")  # text in → 24 kHz PCM out
await tts.interrupt()                                  # cancel on user barge-in
```

Full worked example with the transcript callback and barge-in handling is in
the [`vocence-plugins` README](https://github.com/concil859856/vocence-agents-plugins#using-the-plug-ins-to-build-a-voice-agent).

## CLI

```bash
$ vocence login                          # opens a browser → approve → key saved
$ vocence account                        # show plan, credits remaining, key count
$ vocence usage                          # last 20 API requests
$ vocence keys list / create / revoke
$ vocence agents list / show / create / delete

# voices
$ vocence voices                         # list built-in speakers
$ vocence speak "Hello" --voice design-aria -o out.wav
$ vocence clone path/to/clip.wav --name "My Voice"
$ vocence design "warm female narrator"   # interactive design + save

# audio
$ vocence transcribe clip.wav --language English
$ vocence chat <agent-id>                 # text REPL, plays the reply
$ vocence voice <agent-id>                # push-to-talk mic REPL  (needs vocence[audio])
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
