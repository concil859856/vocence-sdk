"""Shared pytest fixtures.

Tests run against ``respx`` mocks so they never touch the live API. The
``BASE_URL`` constant is the only place we lock to a specific host."""

from __future__ import annotations

import pytest

from vocence import AsyncVocence, Vocence

BASE_URL = "https://api.test.vocence.ai"
API_KEY = "voc_live_test_0000000000000000000000000000"


@pytest.fixture
def client() -> Vocence:
    return Vocence(api_key=API_KEY, base_url=BASE_URL)


@pytest.fixture
async def aclient() -> AsyncVocence:
    return AsyncVocence(api_key=API_KEY, base_url=BASE_URL)
