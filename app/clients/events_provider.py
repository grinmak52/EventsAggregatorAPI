from collections.abc import AsyncIterator
from datetime import date

import httpx


class ProviderError(Exception):
    """Ошибка при обращении к Events Provider API."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class EventsProviderClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 60.0):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"x-api-key": api_key},
            timeout=timeout,
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        try:
            response = await self._client.request(method, url, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            raise ProviderError(f"Провайдер вернул {status}", status_code=status) from e
        except httpx.RequestError as e:
            raise ProviderError(f"Ошибка сети: {type(e).__name__}") from e
        return response.json()

    async def iter_events(self, changed_at: date) -> AsyncIterator[dict]:
        """Отдаёт мероприятия по одному, проходя все страницы по `next`."""
        url: str | None = "/api/events/"
        params: dict | None = {"changed_at": changed_at.isoformat()}
        while url:
            data = await self._request("GET", url, params=params)
            for event in data["results"]:
                yield event
            url = data.get("next")
            params = None  # в `next` параметры уже есть

    async def get_seats(self, event_id: str) -> dict:
        return await self._request("GET", f"/api/events/{event_id}/seats/")

    async def register(
        self, event_id: str, first_name: str, last_name: str, email: str, seat: str
    ) -> dict:
        body = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "seat": seat,
        }
        return await self._request(
            "POST", f"/api/events/{event_id}/register/", json=body
        )

    async def unregister(self, event_id: str, ticket_id: str) -> dict:
        return await self._request(
            "DELETE",
            f"/api/events/{event_id}/unregister/",
            json={"ticket_id": ticket_id},
        )
