"""Account snapshot + API-key management."""

from __future__ import annotations

import httpx
import respx

from vocence import Vocence

from .conftest import API_KEY, BASE_URL


def test_account_get() -> None:
    payload = {
        "user_id": "u1",
        "email": "a@b.com",
        "name": "Alice",
        "credits": 99000,
        "plan_code": "premium",
        "plan_status": "active",
        "api_keys_count": 2,
    }
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        router.get("/v1/account").mock(return_value=httpx.Response(200, json=payload))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        a = client.account.get()
        assert a.credits == 99000
        assert a.plan_code == "premium"


def test_keys_list() -> None:
    payload = {
        "keys": [
            {
                "id": "k1",
                "name": "laptop",
                "key_prefix": "voc_live_AAAA",
                "tier": "normal",
                "rate_limit_rpm": 60,
                "revoked_at": None,
                "created_at": "2026-05-15",
            }
        ]
    }
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        router.get("/v1/account/keys").mock(return_value=httpx.Response(200, json=payload))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        items = client.account.keys.list()
        assert items[0].id == "k1"
        assert items[0].tier == "normal"


def test_keys_create_returns_plaintext_once() -> None:
    payload = {
        "key": {"id": "k2", "name": "ci", "key_prefix": "voc_live_BBBB", "tier": "normal"},
        "plain_key": "voc_live_BBBBxxxxxxxxxxxxxxxxxxxxxxxx",
    }
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        route = router.post("/v1/account/keys").mock(return_value=httpx.Response(201, json=payload))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        c = client.account.keys.create(name="ci")
        import json
        body = json.loads(route.calls.last.request.content)
        assert body == {"name": "ci"}
        assert c.plain_key == payload["plain_key"]
        assert c.key.id == "k2"


def test_keys_revoke() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        router.post("/v1/account/keys/k1/revoke").mock(return_value=httpx.Response(200, json={"ok": True}))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        client.account.keys.revoke("k1")  # should not raise
