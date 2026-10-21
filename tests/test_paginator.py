from datetime import date
from unittest.mock import AsyncMock

from app.clients.paginator import EventsPaginator


async def test_paginator_walks_all_pages():
    client = AsyncMock()
    client.events.side_effect = [
        {"results": [{"id": "1"}, {"id": "2"}], "next": "/api/events/?cursor=x"},
        {"results": [{"id": "3"}], "next": None},
    ]

    events = [e async for e in EventsPaginator(client, date(2000, 1, 1))]

    assert [e["id"] for e in events] == ["1", "2", "3"]
    assert client.events.await_count == 2
    client.events.assert_any_await(date(2000, 1, 1), "/api/events/?cursor=x")


async def test_paginator_empty():
    client = AsyncMock()
    client.events.return_value = {"results": [], "next": None}

    events = [e async for e in EventsPaginator(client, date(2000, 1, 1))]

    assert events == []
