"""Retry behavior — 429, transient 5xx, mutation safety."""

from __future__ import annotations

import httpx
import pytest
import respx

from vocence import BadRequestError, RateLimitError, UpstreamError, Vocence
from vocence._errors import APIConnectionError

from .conftest import API_KEY, BASE_URL


# Use a tiny base so the test suite stays fast (50 ms cap on backoff).
_FAST_KW = {"max_retries": 3}
_RESP_OK = {
    "request_id": "ok",
    "audio_url": "x",
    "provider": "Vocence API",
    "credits_remaining": 1,
    "latency_ms": 1,
    "credits_used": 0,
    "request_chars": 1,
}


def _fast_client() -> Vocence:
    c = Vocence(api_key=API_KEY, base_url=BASE_URL, **_FAST_KW)
    c._http._retry_base = 0.001  # cap to ~1ms so tests don't sleep
    c._http._retry_max = 0.005
    return c


def test_get_retries_then_succeeds_on_429() -> None:
    with respx.mock(base_url=BASE_URL) as router:
        route = router.get("/v1/account").mock(
            side_effect=[
                httpx.Response(429, headers={"retry-after": "0"}, json={"detail": "slow down"}),
                httpx.Response(429, json={"detail": "still slow"}),
                httpx.Response(200, json={
                    "user_id": "u", "credits": 1, "plan_code": "p", "plan_status": "active"
                }),
            ]
        )
        a = _fast_client().account.get()
        assert a.user_id == "u"
        assert route.call_count == 3


def test_get_retries_transient_5xx() -> None:
    with respx.mock(base_url=BASE_URL) as router:
        route = router.get("/v1/voices/builtin").mock(
            side_effect=[
                httpx.Response(503, json={"detail": "upstream"}),
                httpx.Response(502, json={"detail": "upstream"}),
                httpx.Response(200, json={"voices": []}),
            ]
        )
        out = _fast_client().voices.builtin()
        assert out == []
        assert route.call_count == 3


def test_post_does_not_retry_on_5xx_by_default() -> None:
    with respx.mock(base_url=BASE_URL) as router:
        route = router.post("/v1/tts/speak").mock(return_value=httpx.Response(503, json={"detail": "down"}))
        client = _fast_client()
        with pytest.raises(UpstreamError):
            client.tts.speak(text="x", voice="design-aria")
        assert route.call_count == 1  # one call, no retry


def test_post_retries_on_429() -> None:
    with respx.mock(base_url=BASE_URL) as router:
        route = router.post("/v1/tts/speak").mock(
            side_effect=[
                httpx.Response(429, headers={"retry-after": "0"}, json={"detail": "rate"}),
                httpx.Response(200, json=_RESP_OK),
            ]
        )
        r = _fast_client().tts.speak(text="x", voice="design-aria")
        assert r.audio_url == "x"
        assert route.call_count == 2


def test_400_is_not_retried() -> None:
    with respx.mock(base_url=BASE_URL) as router:
        route = router.get("/v1/account").mock(return_value=httpx.Response(400, json={"detail": "bad"}))
        with pytest.raises(BadRequestError):
            _fast_client().account.get()
        assert route.call_count == 1


def test_retries_exhausted_raises_last_error() -> None:
    with respx.mock(base_url=BASE_URL) as router:
        router.get("/v1/account").mock(
            return_value=httpx.Response(429, headers={"retry-after": "0"}, json={"detail": "still"})
        )
        with pytest.raises(RateLimitError):
            _fast_client().account.get()


def test_max_retries_zero_disables_retry() -> None:
    with respx.mock(base_url=BASE_URL) as router:
        route = router.get("/v1/account").mock(
            return_value=httpx.Response(429, headers={"retry-after": "0"}, json={"detail": "slow"})
        )
        client = Vocence(api_key=API_KEY, base_url=BASE_URL, max_retries=0)
        with pytest.raises(RateLimitError):
            client.account.get()
        assert route.call_count == 1


def test_last_request_id_picks_up_body_field() -> None:
    with respx.mock(base_url=BASE_URL) as router:
        router.post("/v1/tts/speak").mock(
            return_value=httpx.Response(200, json={**_RESP_OK, "request_id": "abc-123"})
        )
        client = _fast_client()
        client.tts.speak(text="x", voice="design-aria")
        assert client.last_request_id == "abc-123"


def test_last_request_id_falls_back_to_header() -> None:
    payload = {"voices": [{"id": "v", "name": "n", "description": "d"}]}
    with respx.mock(base_url=BASE_URL) as router:
        router.get("/v1/voices/builtin").mock(
            return_value=httpx.Response(200, headers={"X-Request-ID": "hdr-id"}, json=payload)
        )
        client = _fast_client()
        client.voices.builtin()
        assert client.last_request_id == "hdr-id"


def test_connection_error_retries_for_get() -> None:
    calls = {"n": 0}

    def side_effect(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json={"voices": []})

    with respx.mock(base_url=BASE_URL) as router:
        router.get("/v1/voices/builtin").mock(side_effect=side_effect)
        _fast_client().voices.builtin()
        assert calls["n"] == 3
