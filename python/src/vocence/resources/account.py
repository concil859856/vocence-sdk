"""Account / billing / API-key management endpoints.

These talk to the ``/v1/account/*`` developer-API routes, which proxy to
the dashboard-backend under the hood. The SDK's authenticated ``voc_live_…``
key is the only credential required — there's no separate login step.
"""

from __future__ import annotations

from ..types import Account, ApiKey, ApiKeyCreated


class _AccountBase:
    _account_path = "/v1/account"
    _keys_path = "/v1/account/keys"


class _Keys:
    """Sync key-management helper attached to ``AccountResource.keys``."""

    def __init__(self, http: object) -> None:
        self._http = http
        self._path = _AccountBase._keys_path

    def list(self) -> list[ApiKey]:
        data = self._http.request("GET", self._path)  # type: ignore[attr-defined]
        return [ApiKey.model_validate(k) for k in data.get("keys", [])]

    def create(self, *, name: str) -> ApiKeyCreated:
        data = self._http.request("POST", self._path, json={"name": name})  # type: ignore[attr-defined]
        return ApiKeyCreated.model_validate(data)

    def revoke(self, key_id: str) -> None:
        self._http.request("POST", f"{self._path}/{key_id}/revoke")  # type: ignore[attr-defined]


class _AsyncKeys:
    def __init__(self, http: object) -> None:
        self._http = http
        self._path = _AccountBase._keys_path

    async def list(self) -> list[ApiKey]:
        data = await self._http.request("GET", self._path)  # type: ignore[attr-defined]
        return [ApiKey.model_validate(k) for k in data.get("keys", [])]

    async def create(self, *, name: str) -> ApiKeyCreated:
        data = await self._http.request("POST", self._path, json={"name": name})  # type: ignore[attr-defined]
        return ApiKeyCreated.model_validate(data)

    async def revoke(self, key_id: str) -> None:
        await self._http.request("POST", f"{self._path}/{key_id}/revoke")  # type: ignore[attr-defined]


class AccountResource(_AccountBase):
    def __init__(self, http: object) -> None:
        self._http = http
        self.keys = _Keys(http)

    def get(self) -> Account:
        """Current credits, plan code/status, and key count."""
        data = self._http.request("GET", self._account_path)  # type: ignore[attr-defined]
        return Account.model_validate(data)


class AsyncAccountResource(_AccountBase):
    def __init__(self, http: object) -> None:
        self._http = http
        self.keys = _AsyncKeys(http)

    async def get(self) -> Account:
        data = await self._http.request("GET", self._account_path)  # type: ignore[attr-defined]
        return Account.model_validate(data)
