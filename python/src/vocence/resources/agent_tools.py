"""Custom-tool CRUD — ``/v1/agent-tools``. These are user-defined webhook
tools that any agent can be granted access to via the binding endpoints
on :mod:`.agents`."""

from __future__ import annotations

from typing import Any

from ..types import CustomTool


class _AgentToolsBase:
    _path = "/v1/agent-tools"


class AgentToolsResource(_AgentToolsBase):
    def __init__(self, http: object) -> None:
        self._http = http

    def list(self) -> list[CustomTool]:
        data = self._http.request("GET", self._path)  # type: ignore[attr-defined]
        return [CustomTool.model_validate(t) for t in data.get("tools", [])]

    def get(self, tool_id: str) -> CustomTool:
        data = self._http.request("GET", f"{self._path}/{tool_id}")  # type: ignore[attr-defined]
        return CustomTool.model_validate(data.get("tool") or data)

    def create(
        self,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any],
        endpoint_url: str,
        method: str = "POST",
        auth_type: str = "none",
        auth_header_name: str | None = None,
        auth_secret: str | None = None,
        timeout_ms: int = 5000,
    ) -> CustomTool:
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "endpoint_url": endpoint_url,
            "method": method,
            "auth_type": auth_type,
            "timeout_ms": timeout_ms,
        }
        if auth_header_name is not None:
            body["auth_header_name"] = auth_header_name
        if auth_secret is not None:
            body["auth_secret"] = auth_secret
        data = self._http.request("POST", self._path, json=body)  # type: ignore[attr-defined]
        return CustomTool.model_validate(data.get("tool") or data)

    def update(self, tool_id: str, **fields: Any) -> CustomTool:
        """Partial update. Pass any subset of the create-time fields
        (``description``, ``endpoint_url``, ``method``, ``parameters``,
        ``auth_type``, ``auth_header_name``, ``auth_secret``,
        ``timeout_ms``). Omitted fields stay as-is."""
        data = self._http.request(  # type: ignore[attr-defined]
            "PATCH",
            f"{self._path}/{tool_id}",
            json=fields,
        )
        return CustomTool.model_validate(data.get("tool") or data)

    def delete(self, tool_id: str) -> None:
        self._http.request("DELETE", f"{self._path}/{tool_id}")  # type: ignore[attr-defined]


class AsyncAgentToolsResource(_AgentToolsBase):
    def __init__(self, http: object) -> None:
        self._http = http

    async def list(self) -> list[CustomTool]:
        data = await self._http.request("GET", self._path)  # type: ignore[attr-defined]
        return [CustomTool.model_validate(t) for t in data.get("tools", [])]

    async def get(self, tool_id: str) -> CustomTool:
        data = await self._http.request("GET", f"{self._path}/{tool_id}")  # type: ignore[attr-defined]
        return CustomTool.model_validate(data.get("tool") or data)

    async def create(
        self,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any],
        endpoint_url: str,
        method: str = "POST",
        auth_type: str = "none",
        auth_header_name: str | None = None,
        auth_secret: str | None = None,
        timeout_ms: int = 5000,
    ) -> CustomTool:
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "endpoint_url": endpoint_url,
            "method": method,
            "auth_type": auth_type,
            "timeout_ms": timeout_ms,
        }
        if auth_header_name is not None:
            body["auth_header_name"] = auth_header_name
        if auth_secret is not None:
            body["auth_secret"] = auth_secret
        data = await self._http.request("POST", self._path, json=body)  # type: ignore[attr-defined]
        return CustomTool.model_validate(data.get("tool") or data)

    async def update(self, tool_id: str, **fields: Any) -> CustomTool:
        data = await self._http.request(  # type: ignore[attr-defined]
            "PATCH",
            f"{self._path}/{tool_id}",
            json=fields,
        )
        return CustomTool.model_validate(data.get("tool") or data)

    async def delete(self, tool_id: str) -> None:
        await self._http.request("DELETE", f"{self._path}/{tool_id}")  # type: ignore[attr-defined]
