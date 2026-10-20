from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, call
from uuid import uuid4

import pytest

from domain.entities import Event, EventsPage, Place
from domain.exceptions import ProviderResponseError, ProviderUnavailableError
from infrastructure.clients.events_provider import EventsProviderClient
from worker.paginator import EventsPaginator

CHANGED_AT = date(2000, 1, 1)


def make_event(name: str) -> Event:
    now = datetime(2026, 10, 21, tzinfo=UTC)
    place = Place(
        id=uuid4(),
        name="Place",
        city="Moscow",
        address="Address",
        seats_pattern="A1-10",
        created_at=now,
        changed_at=now,
    )
    return Event(
        id=uuid4(),
        name=name,
        place=place,
        event_time=now,
        registration_deadline=now,
        status="published",
        number_of_visitors=0,
        created_at=now,
        changed_at=now,
        status_changed_at=None,
    )


@pytest.fixture
def client() -> AsyncMock:
    return AsyncMock(spec=EventsProviderClient)


async def test_single_page(client):
    client.get_events.side_effect = [
        EventsPage(results=[make_event("a"), make_event("b")], next_cursor=None)
    ]

    names = [e.name async for e in EventsPaginator(client, CHANGED_AT)]

    assert names == ["a", "b"]
    assert client.get_events.await_args_list == [call(CHANGED_AT, None)]


async def test_multiple_pages_follow_cursors(client):
    client.get_events.side_effect = [
        EventsPage(results=[make_event("a")], next_cursor="c1"),
        EventsPage(results=[make_event("b")], next_cursor="c2"),
        EventsPage(results=[make_event("c")], next_cursor=None),
    ]

    names = [e.name async for e in EventsPaginator(client, CHANGED_AT)]

    assert names == ["a", "b", "c"]
    assert client.get_events.await_args_list == [
        call(CHANGED_AT, None),
        call(CHANGED_AT, "c1"),
        call(CHANGED_AT, "c2"),
    ]


async def test_empty_result(client):
    client.get_events.side_effect = [EventsPage(results=[], next_cursor=None)]

    names = [e.name async for e in EventsPaginator(client, CHANGED_AT)]

    assert names == []


async def test_empty_page_in_the_middle_does_not_stop(client):
    client.get_events.side_effect = [
        EventsPage(results=[], next_cursor="c1"),
        EventsPage(results=[make_event("a")], next_cursor=None),
    ]

    names = [e.name async for e in EventsPaginator(client, CHANGED_AT)]

    assert names == ["a"]


async def test_repeated_cursor_raises(client):
    client.get_events.side_effect = [
        EventsPage(results=[make_event("a")], next_cursor="c1"),
        EventsPage(results=[make_event("b")], next_cursor="c1"),
    ]

    with pytest.raises(ProviderResponseError):
        async for _ in EventsPaginator(client, CHANGED_AT):
            pass


async def test_client_error_propagates(client):
    client.get_events.side_effect = ProviderUnavailableError("down")

    with pytest.raises(ProviderUnavailableError):
        async for _ in EventsPaginator(client, CHANGED_AT):
            pass


async def test_does_not_request_until_iterated(client):
    EventsPaginator(client, CHANGED_AT)

    client.get_events.assert_not_awaited()
