"""Agents + custom-tool CRUD + binding."""

from __future__ import annotations

import httpx
import respx

from vocence import Vocence

from .conftest import API_KEY, BASE_URL

_AGENT = {
    "agent": {
        "id": "a1",
        "type": "knowledge",
        "status": "active",
        "name": "Test",
        "config": {"purpose": "p", "system_prompt": "sp", "knowledge": "", "voice": "design-aria",
                   "language": "English", "llm_model": None, "temperature": 0.4,
                   "enabled_tools": ["web_search"], "goal": None, "success_metric": None, "max_iterations": None},
        "created_at": "2026-05-15", "updated_at": "2026-05-15",
        "last_run_at": None, "run_count": 0, "custom_tools": [],
    }
}


def test_list_agents_returns_summary() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        router.get("/v1/agents").mock(return_value=httpx.Response(
            200, json={"agents": [{"id": "a1", "name": "Test"}]}
        ))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        out = client.agents.list()
        assert out[0].id == "a1"
        assert out[0].name == "Test"


def test_get_agent_returns_full_spec() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        router.get("/v1/agents/a1").mock(return_value=httpx.Response(200, json=_AGENT))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        a = client.agents.get("a1")
        assert a.config.temperature == 0.4
        assert a.config.enabled_tools == ["web_search"]


def test_create_drops_none_fields() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        route = router.post("/v1/agents").mock(return_value=httpx.Response(201, json=_AGENT))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        client.agents.create(name="Test", type="knowledge", voice="design-aria")
        import json
        body = json.loads(route.calls.last.request.content)
        # None-valued fields should NOT be sent
        assert body == {"name": "Test", "type": "knowledge", "voice": "design-aria"}


def test_bind_and_unbind_tool() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        bind = router.post("/v1/agents/a1/tools/t1").mock(return_value=httpx.Response(201, json={"ok": True}))
        unbind = router.delete("/v1/agents/a1/tools/t1").mock(return_value=httpx.Response(200, json={"ok": True}))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        client.agents.tools("a1").bind("t1")
        client.agents.tools("a1").unbind("t1")
        assert bind.called and unbind.called
