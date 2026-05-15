"""v0.4 additions — health, estimate, batch, voice_clone URL, webhooks."""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from vocence import AsyncVocence, Vocence, batch, webhooks
from vocence.resources.tts import Estimate

from .conftest import API_KEY, BASE_URL

# ----- health ----------------------------------------------------------


def test_health_returns_true_on_200() -> None:
    with respx.mock(base_url=BASE_URL) as router:
        router.get("/v1/account").mock(return_value=httpx.Response(
            200, json={"user_id": "u", "credits": 1, "plan_code": "p", "plan_status": "active"}
        ))
        c = Vocence(api_key=API_KEY, base_url=BASE_URL)
        assert c.health() is True
        c.close()


def test_health_returns_false_on_401() -> None:
    with respx.mock(base_url=BASE_URL) as router:
        router.get("/v1/account").mock(return_value=httpx.Response(401, json={"detail": "bad"}))
        c = Vocence(api_key=API_KEY, base_url=BASE_URL, max_retries=0)
        assert c.health() is False
        c.close()


# ----- estimate --------------------------------------------------------


def test_estimate_speak_returns_speak_endpoint() -> None:
    e = Vocence(api_key=API_KEY, base_url=BASE_URL).tts.estimate(text="hello", voice="design-aria")
    assert isinstance(e, Estimate)
    assert e.endpoint == "/v1/tts/speak"
    assert e.credits == 25
    assert e.chars == 5


def test_estimate_generate_no_voice() -> None:
    e = Vocence(api_key=API_KEY, base_url=BASE_URL).tts.estimate(
        text="hello", style_instruction="warm narrator"
    )
    assert e.endpoint == "/v1/tts/generate"
    assert e.credits == 25
    assert e.chars == 5 + len("warm narrator")


# ----- batch -----------------------------------------------------------


async def test_batch_tts_speak_runs_concurrently_and_orders() -> None:
    payload = {
        "request_id": "r", "audio_url": "u", "provider": "Vocence API",
        "credits_remaining": 1, "latency_ms": 1, "credits_used": 0, "request_chars": 1,
    }
    with respx.mock(base_url=BASE_URL) as router:
        router.post("/v1/tts/speak").mock(return_value=httpx.Response(200, json=payload))
        async with AsyncVocence(api_key=API_KEY, base_url=BASE_URL) as client:
            items = [{"text": str(i), "voice": "design-aria"} for i in range(5)]
            results = await batch.tts_speak(client, items, max_concurrency=2)
        assert len(results) == 5
        assert all(getattr(r, "audio_url", None) == "u" for r in results)


async def test_batch_surfaces_per_item_errors() -> None:
    calls = {"n": 0}

    def side(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        # Odd-index calls fail.
        if calls["n"] % 2 == 0:
            return httpx.Response(401, json={"detail": "nope"})
        return httpx.Response(200, json={
            "request_id": "r", "audio_url": "u", "provider": "Vocence API",
            "credits_remaining": 1, "latency_ms": 1, "credits_used": 0, "request_chars": 1,
        })

    with respx.mock(base_url=BASE_URL) as router:
        router.post("/v1/tts/speak").mock(side_effect=side)
        async with AsyncVocence(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
            items = [{"text": str(i), "voice": "design-aria"} for i in range(4)]
            results = await batch.tts_speak(client, items, max_concurrency=1)
        ok = [r for r in results if not isinstance(r, batch.BatchError)]
        bad = [r for r in results if isinstance(r, batch.BatchError)]
        assert len(ok) + len(bad) == 4
        assert len(bad) > 0
        # Errors carry the failing item back to the caller for retries.
        assert bad[0].item in items


# ----- webhooks --------------------------------------------------------


def test_webhook_sign_verify_round_trip() -> None:
    body = b'{"ticker":"TSLA"}'
    headers = webhooks.sign(body, secret="shh")
    assert webhooks.verify(headers, body, secret="shh") is True


def test_webhook_rejects_wrong_secret() -> None:
    body = b'{"x":1}'
    headers = webhooks.sign(body, secret="shh")
    assert webhooks.verify(headers, body, secret="other") is False


def test_webhook_rejects_replay_after_tolerance() -> None:
    body = b'{"x":1}'
    headers = webhooks.sign(body, secret="shh", timestamp=int(time.time()) - 1000)
    assert webhooks.verify(headers, body, secret="shh") is False  # default 300s tolerance


def test_webhook_rejects_tampered_body() -> None:
    body = b'{"x":1}'
    headers = webhooks.sign(body, secret="shh")
    assert webhooks.verify(headers, b'{"x":2}', secret="shh") is False


def test_webhook_rejects_missing_headers() -> None:
    assert webhooks.verify({}, b"x", secret="shh") is False
    assert webhooks.verify({"x-vocence-timestamp": "0"}, b"x", secret="shh") is False


def test_webhook_handles_case_insensitive_headers() -> None:
    body = b"x"
    h = webhooks.sign(body, secret="shh")
    # Send the headers back with weird casing — real-world frameworks
    # vary on this.
    h2 = {"X-Vocence-TimeStamp": h["x-vocence-timestamp"],
          "X-Vocence-Signature": h["x-vocence-signature"]}
    assert webhooks.verify(h2, body, secret="shh") is True


# ----- voice clone URL -------------------------------------------------


def test_voice_clone_from_url_downloads_then_posts() -> None:
    fake_audio = b"FAKE_WAV_BYTES"
    clone_resp = {
        "request_id": "r", "audio_url": "https://out/x.wav",
        "reference_text": "hi", "provider": "Vocence API",
        "credits_remaining": 1, "latency_ms": 1, "credits_used": 0,
    }
    with respx.mock() as router:
        router.get("https://src/voice.wav").mock(return_value=httpx.Response(200, content=fake_audio))
        router.post(f"{BASE_URL}/v1/voice/clone").mock(return_value=httpx.Response(200, json=clone_resp))
        c = Vocence(api_key=API_KEY, base_url=BASE_URL)
        r = c.voice_clone.create(
            target_text="hello",
            audio_url="https://src/voice.wav",
        )
        assert r.audio_url == "https://out/x.wav"
        c.close()


def test_voice_clone_requires_exactly_one_source() -> None:
    c = Vocence(api_key=API_KEY, base_url=BASE_URL)
    with pytest.raises(ValueError):
        c.voice_clone.create(target_text="x")
    with pytest.raises(ValueError):
        c.voice_clone.create(target_text="x", audio_bytes=b"a", audio_url="https://x")
    c.close()
