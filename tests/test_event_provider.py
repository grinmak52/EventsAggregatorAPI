from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.clients.events_provider import EventsProviderClient, ProviderError


def make_client(request_mock: AsyncMock) -> EventsProviderClient:
    client = EventsProviderClient("http://provider", "key")
    client._client.request = request_mock
    return client


def ok(data: dict) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = data
    return response


async def test_get_seats_ok():
    client = make_client(AsyncMock(return_value=ok({"seats": ["A1"]})))
    assert await client.get_seats("e1") == {"seats": ["A1"]}


async def test_http_error_becomes_provider_error():
    error_response = MagicMock(status_code=404, text="not found")
    exc = httpx.HTTPStatusError("x", request=MagicMock(), response=error_response)
    response = MagicMock()
    response.raise_for_status.side_effect = exc
    client = make_client(AsyncMock(return_value=response))

    with pytest.raises(ProviderError) as info:
        await client.get_seats("e1")
    assert info.value.status_code == 404


async def test_timeout_becomes_provider_error():
    client = make_client(AsyncMock(side_effect=httpx.ConnectTimeout("boom")))

    with pytest.raises(ProviderError) as info:
        await client.get_seats("e1")
    assert info.value.status_code is None
