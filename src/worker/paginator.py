from collections import deque
from datetime import date
from typing import Self

from domain.entities import Event
from domain.exceptions import ProviderResponseError
from infrastructure.clients.events_provider import EventsProviderClient


class EventsPaginator:
    def __init__(self, client: EventsProviderClient, changed_at: date) -> None:
        self._client = client
        self._changed_at = changed_at
        self._buffer: deque[Event] = deque()
        self._cursor: str | None = None
        self._exhausted = False

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> Event:
        while not self._buffer:
            if self._exhausted:
                raise StopAsyncIteration
            await self._fetch_next_page()
        return self._buffer.popleft()

    async def _fetch_next_page(self) -> None:
        page = await self._client.get_events(self._changed_at, self._cursor)
        if page.next_cursor is not None and page.next_cursor == self._cursor:
            raise ProviderResponseError(
                "Events provider returned the same cursor twice"
            )
        self._buffer.extend(page.results)
        self._cursor = page.next_cursor
        self._exhausted = page.next_cursor is None
