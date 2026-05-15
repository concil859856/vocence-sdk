"""STT endpoint tests — file vs bytes vs base64 input normalization."""

from __future__ import annotations

import base64

import httpx
import pytest
import respx

from vocence import Vocence

from .conftest import API_KEY, BASE_URL

_STT_RESP = {
    "request_id": "abc",
    "text": "hello world",
    "language": "English",
    "provider": "Vocence API",
    "credits_remaining": 99000,
    "latency_ms": 100,
    "credits_used": 20,
}


def test_transcribe_with_bytes() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        route = router.post("/v1/stt/transcribe").mock(return_value=httpx.Response(200, json=_STT_RESP))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        client.stt.transcribe(audio_bytes=b"FAKEWAV", language="English")
        import json
        body = json.loads(route.calls.last.request.content)
        assert body["audio_b64"] == base64.b64encode(b"FAKEWAV").decode()
        assert body["language"] == "English"


def test_transcribe_requires_exactly_one_source() -> None:
    client = Vocence(api_key=API_KEY, base_url=BASE_URL)
    with pytest.raises(ValueError):
        client.stt.transcribe()
    with pytest.raises(ValueError):
        client.stt.transcribe(audio_bytes=b"x", audio_b64="y")


def test_transcribe_with_b64_passes_through() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        route = router.post("/v1/stt/transcribe").mock(return_value=httpx.Response(200, json=_STT_RESP))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        client.stt.transcribe(audio_b64="alreadyencoded")
        import json
        body = json.loads(route.calls.last.request.content)
        assert body["audio_b64"] == "alreadyencoded"
        assert "language" not in body
