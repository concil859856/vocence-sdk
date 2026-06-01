"""Agents — CRUD plus the per-agent tool-binding subroutes and the
real-time WebSocket session helper (async-only)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..types import Agent, AgentSummary, CustomTool

if TYPE_CHECKING:
    from .._live import LiveChat
    from .._streaming import AgentSession
    from .._streaming_sync import SyncAgentSession
    from ..conversation import Conversation


class _AgentsBase:
    _path = "/v1/agents"


# --------------------------------------------------------------------- sync


class _AgentToolBindings:
    """Sync helper for ``/v1/agents/{agent_id}/tools/...`` routes."""

    def __init__(self, http: object, agent_id: str) -> None:
        self._http = http
        self._base = f"/v1/agents/{agent_id}/tools"

    def list(self) -> list[CustomTool]:
        data = self._http.request("GET", self._base)  # type: ignore[attr-defined]
        return [CustomTool.model_validate(t) for t in data.get("tools", [])]

    def bind(self, tool_id: str) -> None:
        self._http.request("POST", f"{self._base}/{tool_id}")  # type: ignore[attr-defined]

    def unbind(self, tool_id: str) -> None:
        self._http.request("DELETE", f"{self._base}/{tool_id}")  # type: ignore[attr-defined]


class _AgentRuns:
    """Sync helper for goal-agent runs:
    ``client.agents.runs(agent_id).{list,start,get,cancel}(...)``.

    Only meaningful for agents whose ``type == 'goal'`` — knowledge
    agents have no run loop, and ``list`` returns ``[]`` for them so
    callers don't need a special-case branch."""

    def __init__(self, http: object, agent_id: str) -> None:
        self._http = http
        self._base = f"/v1/agents/{agent_id}/runs"

    def list(self) -> list[dict]:
        data = self._http.request("GET", self._base)  # type: ignore[attr-defined]
        return list(data.get("runs") or [])

    def start(self) -> dict:
        """Kick off a new run. Returns the run row in ``pending`` state —
        poll :meth:`get` for progress. Raises if the agent is paused /
        archived or has no goal configured."""
        data = self._http.request("POST", self._base, json={})  # type: ignore[attr-defined]
        return dict(data.get("run") or data)

    def get(self, run_id: str) -> dict:
        data = self._http.request("GET", f"{self._base}/{run_id}")  # type: ignore[attr-defined]
        return dict(data.get("run") or data)

    def cancel(self, run_id: str) -> dict:
        """Idempotent — succeeds even if the run already finished."""
        return self._http.request("POST", f"{self._base}/{run_id}/cancel", json={})  # type: ignore[attr-defined]


class AgentsResource(_AgentsBase):
    def __init__(self, http: object, *, base_url: str, api_key: str) -> None:
        self._http = http
        self._base_url = base_url
        self._api_key = api_key

    def list(self) -> list[AgentSummary]:
        data = self._http.request("GET", self._path)  # type: ignore[attr-defined]
        return [AgentSummary.model_validate(a) for a in data.get("agents", [])]

    def get(self, agent_id: str) -> Agent:
        data = self._http.request("GET", f"{self._path}/{agent_id}")  # type: ignore[attr-defined]
        return Agent.model_validate(data.get("agent") or data)

    def create(
        self,
        *,
        name: str,
        type: str,
        purpose: str | None = None,
        system_prompt: str | None = None,
        knowledge: str | None = None,
        voice: str | None = None,
        language: str | None = None,
        llm_model: str | None = None,
        temperature: float | None = None,
        enabled_tools: list[str] | None = None,
        goal: str | None = None,
        success_metric: str | None = None,
        max_iterations: int | None = None,
    ) -> Agent:
        body = _agent_body(
            name=name, type=type, purpose=purpose, system_prompt=system_prompt,
            knowledge=knowledge, voice=voice, language=language,
            llm_model=llm_model, temperature=temperature,
            enabled_tools=enabled_tools, goal=goal,
            success_metric=success_metric, max_iterations=max_iterations,
        )
        data = self._http.request("POST", self._path, json=body)  # type: ignore[attr-defined]
        return Agent.model_validate(data.get("agent") or data)

    def update(self, agent_id: str, **fields: Any) -> Agent:
        """Partial update. Accepts any subset of the create-time fields
        plus ``status`` (``draft|active|paused|archived``)."""
        data = self._http.request(  # type: ignore[attr-defined]
            "PATCH",
            f"{self._path}/{agent_id}",
            json=fields,
        )
        return Agent.model_validate(data.get("agent") or data)

    def delete(self, agent_id: str) -> None:
        self._http.request("DELETE", f"{self._path}/{agent_id}")  # type: ignore[attr-defined]

    def tools(self, agent_id: str) -> _AgentToolBindings:
        """Tool-binding helper: ``client.agents.tools(agent_id).bind(tool_id)``."""
        return _AgentToolBindings(self._http, agent_id)

    def runs(self, agent_id: str) -> _AgentRuns:
        """Goal-agent run helper: ``client.agents.runs(id).start()``."""
        return _AgentRuns(self._http, agent_id)

    # ----- discovery: templates / models / built-in tools -----

    def templates(self) -> list[dict]:
        """Starter-template gallery for an agent-builder UI. Compact
        summaries only — call :meth:`template` for the full body."""
        data = self._http.request("GET", "/v1/agents/templates")  # type: ignore[attr-defined]
        return list(data.get("templates") or [])

    def template(self, template_id: str) -> dict:
        """Full template body (system_prompt + knowledge_starter).
        Snapshot semantics — saved agents own their own copy."""
        return self._http.request(  # type: ignore[attr-defined]
            "GET", f"/v1/agents/templates/{template_id}",
        )

    def models(self) -> list[dict]:
        """LLM models the agent picker offers on this deployment. Pass
        any returned ``id`` as ``llm_model`` to :meth:`create` or
        :meth:`update`."""
        data = self._http.request("GET", "/v1/agents/models")  # type: ignore[attr-defined]
        return list(data.get("models") or [])

    def builtin_tools(self) -> list[dict]:
        """Catalog of built-in tools (web search, weather, datetime,
        etc.). Each entry tells you whether the tool is configured
        server-side. To enable on an agent, list the tool ``id`` in
        ``enabled_tools`` on :meth:`create` / :meth:`update`."""
        data = self._http.request("GET", "/v1/agents/tools/builtin")  # type: ignore[attr-defined]
        return list(data.get("tools") or [])

    # ----- LLM-powered authoring -----

    def draft(
        self,
        description: str,
        *,
        type_hint: str | None = None,
        existing: dict | None = None,
    ) -> dict:
        """One-shot: produce a complete agent spec from a plain-English
        description. For an iterative back-and-forth flow, use
        :meth:`architect_chat` instead."""
        body: dict[str, Any] = {"description": description}
        if type_hint is not None:
            body["type_hint"] = type_hint
        if existing is not None:
            body["existing"] = existing
        return self._http.request("POST", "/v1/agents/draft", json=body)  # type: ignore[attr-defined]

    def architect_chat(
        self,
        message: str,
        *,
        history: list[dict] | None = None,
        existing: dict | None = None,
    ) -> dict:
        """One conversational turn with the architect. Returns
        ``{reply, proposed_changes}``. ``proposed_changes`` is non-None
        only when the architect decided the user is asking for an edit
        — show an "Apply" button to the user in that case, otherwise
        treat ``reply`` as plain conversation."""
        body: dict[str, Any] = {
            "message": message,
            "history": history or [],
        }
        if existing is not None:
            body["existing"] = existing
        return self._http.request(  # type: ignore[attr-defined]
            "POST", "/v1/agents/architect/chat", json=body,
        )

    def knowledge(self, agent_id: str) -> "KnowledgeResource":
        """Knowledge-ingest helper: ``client.agents.knowledge(id).ingest_url(...)``."""
        from .knowledge import KnowledgeResource
        return KnowledgeResource(self._http, agent_id)

    def embed_tokens(self, agent_id: str) -> "EmbedTokensResource":
        """Embed-token helper: ``client.agents.embed_tokens(id).create(...)``."""
        from .embed_tokens import EmbedTokensResource
        return EmbedTokensResource(self._http, agent_id)

    def session(self, agent_id: str) -> SyncAgentSession:
        """Open a blocking WebSocket session with an agent.

        Use as a regular context manager::

            with client.agents.session("agent-id") as sess:
                sess.send_text("hi")
                for event in sess:
                    print(event)
                    if event.type == "turn_end":
                        break

        Async callers should use :class:`AsyncVocence` and
        ``await client.agents.session(...)`` instead — that path is the
        native flow and avoids the extra thread this wrapper spins up.
        """
        # Local import to keep `websockets` optional for REST-only users.
        from .._streaming_sync import SyncAgentSession

        ws_url = self._base_url.replace("http://", "ws://").replace("https://", "wss://")
        return SyncAgentSession(
            url=f"{ws_url}/v1/agents/{agent_id}/session",
            api_key=self._api_key,
        )


# -------------------------------------------------------------------- async


class _AsyncAgentToolBindings:
    def __init__(self, http: object, agent_id: str) -> None:
        self._http = http
        self._base = f"/v1/agents/{agent_id}/tools"

    async def list(self) -> list[CustomTool]:
        data = await self._http.request("GET", self._base)  # type: ignore[attr-defined]
        return [CustomTool.model_validate(t) for t in data.get("tools", [])]

    async def bind(self, tool_id: str) -> None:
        await self._http.request("POST", f"{self._base}/{tool_id}")  # type: ignore[attr-defined]

    async def unbind(self, tool_id: str) -> None:
        await self._http.request("DELETE", f"{self._base}/{tool_id}")  # type: ignore[attr-defined]


class _AsyncAgentRuns:
    """Async sibling of :class:`_AgentRuns`."""

    def __init__(self, http: object, agent_id: str) -> None:
        self._http = http
        self._base = f"/v1/agents/{agent_id}/runs"

    async def list(self) -> list[dict]:
        data = await self._http.request("GET", self._base)  # type: ignore[attr-defined]
        return list(data.get("runs") or [])

    async def start(self) -> dict:
        data = await self._http.request("POST", self._base, json={})  # type: ignore[attr-defined]
        return dict(data.get("run") or data)

    async def get(self, run_id: str) -> dict:
        data = await self._http.request("GET", f"{self._base}/{run_id}")  # type: ignore[attr-defined]
        return dict(data.get("run") or data)

    async def cancel(self, run_id: str) -> dict:
        return await self._http.request(  # type: ignore[attr-defined]
            "POST", f"{self._base}/{run_id}/cancel", json={},
        )


class AsyncAgentsResource(_AgentsBase):
    def __init__(self, http: object, *, base_url: str, api_key: str) -> None:
        self._http = http
        self._base_url = base_url
        self._api_key = api_key

    async def list(self) -> list[AgentSummary]:
        data = await self._http.request("GET", self._path)  # type: ignore[attr-defined]
        return [AgentSummary.model_validate(a) for a in data.get("agents", [])]

    async def get(self, agent_id: str) -> Agent:
        data = await self._http.request("GET", f"{self._path}/{agent_id}")  # type: ignore[attr-defined]
        return Agent.model_validate(data.get("agent") or data)

    async def create(
        self,
        *,
        name: str,
        type: str,
        purpose: str | None = None,
        system_prompt: str | None = None,
        knowledge: str | None = None,
        voice: str | None = None,
        language: str | None = None,
        llm_model: str | None = None,
        temperature: float | None = None,
        enabled_tools: list[str] | None = None,
        goal: str | None = None,
        success_metric: str | None = None,
        max_iterations: int | None = None,
    ) -> Agent:
        body = _agent_body(
            name=name, type=type, purpose=purpose, system_prompt=system_prompt,
            knowledge=knowledge, voice=voice, language=language,
            llm_model=llm_model, temperature=temperature,
            enabled_tools=enabled_tools, goal=goal,
            success_metric=success_metric, max_iterations=max_iterations,
        )
        data = await self._http.request("POST", self._path, json=body)  # type: ignore[attr-defined]
        return Agent.model_validate(data.get("agent") or data)

    async def update(self, agent_id: str, **fields: Any) -> Agent:
        data = await self._http.request(  # type: ignore[attr-defined]
            "PATCH",
            f"{self._path}/{agent_id}",
            json=fields,
        )
        return Agent.model_validate(data.get("agent") or data)

    async def delete(self, agent_id: str) -> None:
        await self._http.request("DELETE", f"{self._path}/{agent_id}")  # type: ignore[attr-defined]

    def tools(self, agent_id: str) -> _AsyncAgentToolBindings:
        return _AsyncAgentToolBindings(self._http, agent_id)

    def runs(self, agent_id: str) -> _AsyncAgentRuns:
        return _AsyncAgentRuns(self._http, agent_id)

    # ----- discovery -----

    async def templates(self) -> list[dict]:
        data = await self._http.request("GET", "/v1/agents/templates")  # type: ignore[attr-defined]
        return list(data.get("templates") or [])

    async def template(self, template_id: str) -> dict:
        return await self._http.request(  # type: ignore[attr-defined]
            "GET", f"/v1/agents/templates/{template_id}",
        )

    async def models(self) -> list[dict]:
        data = await self._http.request("GET", "/v1/agents/models")  # type: ignore[attr-defined]
        return list(data.get("models") or [])

    async def builtin_tools(self) -> list[dict]:
        data = await self._http.request("GET", "/v1/agents/tools/builtin")  # type: ignore[attr-defined]
        return list(data.get("tools") or [])

    # ----- LLM-powered authoring -----

    async def draft(
        self,
        description: str,
        *,
        type_hint: str | None = None,
        existing: dict | None = None,
    ) -> dict:
        body: dict[str, Any] = {"description": description}
        if type_hint is not None:
            body["type_hint"] = type_hint
        if existing is not None:
            body["existing"] = existing
        return await self._http.request("POST", "/v1/agents/draft", json=body)  # type: ignore[attr-defined]

    async def architect_chat(
        self,
        message: str,
        *,
        history: list[dict] | None = None,
        existing: dict | None = None,
    ) -> dict:
        body: dict[str, Any] = {
            "message": message,
            "history": history or [],
        }
        if existing is not None:
            body["existing"] = existing
        return await self._http.request(  # type: ignore[attr-defined]
            "POST", "/v1/agents/architect/chat", json=body,
        )

    def knowledge(self, agent_id: str) -> "AsyncKnowledgeResource":
        """Async knowledge-ingest helper: ``await client.agents.knowledge(id).ingest_url(...)``."""
        from .knowledge import AsyncKnowledgeResource
        return AsyncKnowledgeResource(self._http, agent_id)

    def embed_tokens(self, agent_id: str) -> "AsyncEmbedTokensResource":
        """Async embed-token helper: ``await client.agents.embed_tokens(id).create(...)``."""
        from .embed_tokens import AsyncEmbedTokensResource
        return AsyncEmbedTokensResource(self._http, agent_id)

    def session(self, agent_id: str) -> AgentSession:
        """Open a real-time voice / text WebSocket session with an agent.

        Use as an async context manager::

            async with client.agents.session("agent-id") as sess:
                await sess.send_text("hi")
                async for event in sess:
                    print(event)
        """
        # Local import to avoid a hard dependency on `websockets` when the
        # caller only uses the REST surface.
        from .._streaming import AgentSession

        ws_url = self._base_url.replace("http://", "ws://").replace("https://", "wss://")
        return AgentSession(
            url=f"{ws_url}/v1/agents/{agent_id}/session",
            api_key=self._api_key,
        )

    def conversation(self, agent_id: str) -> Conversation:
        """High-level voice chat. Same WS connection under the hood as
        :meth:`session`, but you get :meth:`Conversation.say` /
        :meth:`Conversation.send_voice` that block until the assistant
        finishes a turn and return an aggregated :class:`Turn` object
        (text, full audio bytes, tool calls). For token-level streaming
        drop down to :meth:`session` instead."""
        from ..conversation import Conversation

        return Conversation(self.session(agent_id))

    def live_chat(self, agent_id: str) -> LiveChat:
        """Open a microphone-in / speaker-out session with an agent.

        Requires ``pip install vocence[audio]`` for ``sounddevice`` +
        ``numpy``. Push-to-talk: call :meth:`LiveChat.record` to start
        capturing, then :meth:`LiveChat.stop_and_send` to ship the clip
        and hear the reply played back through the default audio device."""
        from .._live import LiveChat

        return LiveChat(self.session(agent_id))


# --------------------------------------------------------------- helpers


def _agent_body(**fields: Any) -> dict[str, Any]:
    """Drop None values so the server-side ``patch`` semantics work — only
    fields the caller actually specified are sent on the wire."""
    return {k: v for k, v in fields.items() if v is not None}
