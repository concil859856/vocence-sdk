"""Voices catalog + saved voice CRUD."""

from __future__ import annotations

import httpx
import respx

from vocence import Vocence

from .conftest import API_KEY, BASE_URL


def test_builtin_returns_typed_list() -> None:
    payload = {
        "voices": [
            {"id": "design-aria", "name": "Aria", "description": "Bright, energetic female"},
            {"id": "design-marcus", "name": "Marcus", "description": "Mature male"},
        ]
    }
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        router.get("/v1/voices/builtin").mock(return_value=httpx.Response(200, json=payload))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        items = client.voices.builtin()
        assert [v.id for v in items] == ["design-aria", "design-marcus"]
        assert items[0].name == "Aria"


def test_list_saved_voices() -> None:
    payload = {
        "voices": [
            {
                "id": 7,
                "display_name": "My Voice",
                "source": "cloned",
                "ref_script": "hi",
                "source_language": "English",
            },
        ]
    }
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        router.get("/v1/voices").mock(return_value=httpx.Response(200, json=payload))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        v = client.voices.list()
        assert v[0].id == 7
        assert v[0].source == "cloned"


def test_speak_with_saved_voice() -> None:
    payload = {
        "id": 99,
        "audio_url": "https://example/out.wav",
        "credits": 99000,
    }
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        route = router.post("/v1/voices/7/speak").mock(return_value=httpx.Response(200, json=payload))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        r = client.voices.speak(7, text="hello")
        import json
        body = json.loads(route.calls.last.request.content)
        assert body == {"text": "hello"}
        assert r.audio_url == "https://example/out.wav"


def test_delete_saved_voice() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        router.delete("/v1/voices/7").mock(return_value=httpx.Response(200, json={"ok": True}))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        client.voices.delete(7)  # should not raise
