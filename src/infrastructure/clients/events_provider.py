import logging
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from pydantic import BaseModel, ValidationError

from core.config import EventsProviderConfig
from domain.entities import Event, EventsPage
from domain.exceptions import (
    ProviderBadRequestError,
    ProviderError,
    ProviderNotFoundError,
    ProviderResponseError,
    ProviderUnauthorizedError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class _EventsResponse(BaseModel):
    next: str | None = None
    results: list[Event]


class _SeatsResponse(BaseModel):
    seats: list[str]


class _RegisterResponse(BaseModel):
    ticket_id: str


def create_http_client(config: EventsProviderConfig) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=config.base_url,
        headers={"x-api-key": config.api_key.get_secret_value()},
        timeout=config.timeout,
    )


def _extract_cursor(next_url: str | None) -> str | None:
    if next_url is None:
        return None
    values = parse_qs(urlparse(next_url).query).get("cursor")
    if not values:
        raise ProviderResponseError("Events provider returned 'next' without a cursor")
    return values[0]


class EventsProviderClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client

    async def get_events(
        self, changed_at: date, cursor: str | None = None
    ) -> EventsPage:
        params = {"changed_at": changed_at.isoformat()}
        if cursor is not None:
            params["cursor"] = cursor
        response = await self._request("GET", "/api/events/", params=params)
        payload = self._parse(_EventsResponse, response)
        return EventsPage(
            results=payload.results,
            next_cursor=_extract_cursor(payload.next),
        )

    async def get_seats(self, event_id: str) -> list[str]:
        response = await self._request("GET", f"/api/events/{event_id}/seats/")
        return self._parse(_SeatsResponse, response).seats

    async def register(
        self,
        event_id: str,
        first_name: str,
        last_name: str,
        email: str,
        seat: str,
    ) -> str:
        response = await self._request(
            "POST",
            f"/api/events/{event_id}/register/",
            json={
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "seat": seat,
            },
        )
        return self._parse(_RegisterResponse, response).ticket_id

    async def unregister(self, event_id: str, ticket_id: str) -> None:
        await self._request(
            "DELETE",
            f"/api/events/{event_id}/unregister/",
            json={"ticket_id": ticket_id},
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            logger.error("Events provider timeout: %s %s", method, path)
            raise ProviderUnavailableError("Events provider timed out") from exc
        except httpx.TransportError as exc:
            logger.error("Events provider unreachable: %s %s", method, path)
            raise ProviderUnavailableError("Events provider is unreachable") from exc
        self._raise_for_status(response)
        return response

    def _raise_for_status(self, response: httpx.Response) -> None:
        status = response.status_code
        if status < 300:
            return
        request = response.request
        detail = response.text[:200]
        logger.warning(
            "Events provider %s %s -> %s: %s",
            request.method,
            request.url.path,
            status,
            detail,
        )
        if status < 400:
            raise ProviderError(
                f"Unexpected redirect ({status}); check the provider "
                "base URL and trailing slashes"
            )
        if status in (401, 403):
            raise ProviderUnauthorizedError("Events provider rejected the API key")
        if status == 404:
            raise ProviderNotFoundError("Not found in events provider")
        if status < 500:
            raise ProviderBadRequestError(
                f"Events provider rejected the request ({status}): {detail}"
            )
        raise ProviderUnavailableError(f"Events provider failed with status {status}")

    def _parse[T: BaseModel](self, model: type[T], response: httpx.Response) -> T:
        try:
            return model.model_validate_json(response.content)
        except ValidationError as exc:
            logger.error("Unexpected events provider response: %s", exc)
            raise ProviderResponseError(
                "Unexpected response format from events provider"
            ) from exc
