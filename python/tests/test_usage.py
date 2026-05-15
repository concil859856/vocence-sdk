"""Usage endpoint — both the request body shape and the limit clamp."""

from __future__ import annotations

import httpx
import respx

from vocence import Vocence

from .conftest import API_KEY, BASE_URL

_PAYLOAD = {
    "items": [
        {
            "id": "r1",
            "endpoint": "/v1/tts/speak",
            "provider": "Vocence API",
            "status": "success",
            "http_status": 200,
            "credits_used": 25,
            "request_chars": 12,
            "latency_ms": 800,
            "error_code": None,
            "error_message": None,
            "created_at": "2026-05-15 12:00:00",
        }
    ]
}


def test_usage_default_limit() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        route = router.get("/v1/account/usage").mock(return_value=httpx.Response(200, json=_PAYLOAD))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        rows = client.account.usage()
        assert rows[0].endpoint == "/v1/tts/speak"
        assert rows[0].credits_used == 25
        # limit=50 default passed as query param
        params = dict(route.calls.last.request.url.params)
        assert params == {"limit": "50"}


def test_usage_custom_limit() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        route = router.get("/v1/account/usage").mock(return_value=httpx.Response(200, json=_PAYLOAD))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        client.account.usage(limit=5)
        assert dict(route.calls.last.request.url.params) == {"limit": "5"}
