"""HTTP-status → exception mapping."""

from __future__ import annotations

import httpx
import pytest
import respx

from vocence import (
    AuthenticationError,
    BadRequestError,
    InsufficientCreditsError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UpstreamError,
    Vocence,
    VocenceError,
)

from .conftest import API_KEY, BASE_URL


@pytest.mark.parametrize(
    "status,exc,detail",
    [
        (400, BadRequestError, "bad payload"),
        (401, AuthenticationError, "invalid key"),
        (402, InsufficientCreditsError, "need premium"),
        (403, PermissionDeniedError, "revoked"),
        (404, NotFoundError, "missing"),
        (422, BadRequestError, "invalid field"),
        (502, UpstreamError, "provider down"),
        (503, UpstreamError, "voice clone unavailable"),
    ],
)
def test_status_maps_to_exception(status: int, exc: type, detail: str) -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        router.get("/v1/account").mock(return_value=httpx.Response(status, json={"detail": detail}))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        with pytest.raises(exc) as ex:
            client.account.get()
        assert ex.value.status_code == status
        assert detail in str(ex.value)


def test_rate_limit_carries_retry_after() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        router.get("/v1/account").mock(
            return_value=httpx.Response(429, headers={"retry-after": "12"}, json={"detail": "slow down"})
        )
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        with pytest.raises(RateLimitError) as ex:
            client.account.get()
        assert ex.value.retry_after == 12.0


def test_unknown_status_falls_back_to_base() -> None:
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        router.get("/v1/account").mock(return_value=httpx.Response(418, json={"detail": "teapot"}))
        client = Vocence(api_key=API_KEY, base_url=BASE_URL)
        with pytest.raises(VocenceError) as ex:
            client.account.get()
        assert ex.value.status_code == 418
