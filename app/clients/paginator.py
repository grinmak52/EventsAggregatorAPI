from collections.abc import AsyncIterator
from datetime import date
from typing import Protocol


class PageClient(Protocol):
    async def events(self, changed_at: date, cursor: str | None = None) -> dict: ...


class EventsPaginator:
    def __init__(self, client: PageClient, changed_at: date):
        self._client = client
        self._changed_at = changed_at

    async def __aiter__(self) -> AsyncIterator[dict]:
        cursor = None
        while True:
            page = await self._client.events(self._changed_at, cursor)
            for event in page["results"]:
                yield event
            cursor = page.get("next")
            if not cursor:
                break
