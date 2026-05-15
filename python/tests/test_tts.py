"""TTS endpoint tests — sync + async, generate + speak."""

from __future__ import annotations

import httpx
import respx

from vocence import AsyncVocence, Vocence

from .conftest import API_KEY, BASE_URL

_TTS_RESP = {
    "request_id": "abc",
    "audio_url": "https://example/x.wav",
    "provider": "Vocence API",
    "credits_remaining": 99000,
    "latency_ms": 12,
    "credits_used": 25,
    "request_chars": 5,
}


def test_generate_posts_text_and_style() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        route = router.post("/v1/tts/generate").mock(return_value=httpx.Response(200, json=_TTS_RESP))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        r = client.tts.generate(text="Hi", style_instruction="warm narrator")
        # Bearer header
        sent = route.calls.last.request
        assert sent.headers["authorization"] == f"Bearer {API_KEY}"
        # Body shape
        import json
        body = json.loads(sent.content)
        assert body == {"text": "Hi", "style_instruction": "warm narrator"}
        # Parsed response
        assert r.audio_url == "https://example/x.wav"
        assert r.provider == "Vocence API"


def test_speak_requires_voice() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        route = router.post("/v1/tts/speak").mock(return_value=httpx.Response(200, json=_TTS_RESP))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        client.tts.speak(text="Hi", voice="design-aria")
        import json
        body = json.loads(route.calls.last.request.content)
        assert body == {"text": "Hi", "voice": "design-aria"}


async def test_async_speak_works() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        router.post("/v1/tts/speak").mock(return_value=httpx.Response(200, json=_TTS_RESP))
        async with AsyncVocence(api_key=API_KEY, base_url=BASE_URL) as client:
            r = await client.tts.speak(text="Hi", voice="design-aria")
        assert r.audio_url == "https://example/x.wav"
