from datetime import date
from uuid import UUID

import httpx
import pytest

from domain.entities import EventsPage
from domain.exceptions import (
    ProviderBadRequestError,
    ProviderError,
    ProviderNotFoundError,
    ProviderResponseError,
    ProviderUnauthorizedError,
    ProviderUnavailableError,
)
from infrastructure.clients.events_provider import EventsProviderClient

BASE_URL = "http://provider.test"
EVENT_ID = "59314ca0-5569-449d-ab26-190716a8ea16"
TICKET_ID = "0f9c5f5e-8a0e-4a8e-9d57-6a4b1f0f6c11"

EVENT_PAYLOAD = {
    "id": EVENT_ID,
    "place": {
        "id": "fd2dc4aa-39fb-40ef-86b9-c690bd0d1bdc",
        "changed_at": "2025-01-01T03:00:00+03:00",
        "created_at": "2025-01-01T03:00:00+03:00",
        "name": "Фетисов Арена",
        "city": "Владивосток",
        "address": "ул. Катерная, 4",
        "seats_pattern": "A1-250,B1-500",
    },
    "changed_at": "2026-10-21T00:00:00.400122+03:00",
    "created_at": "2026-10-21T00:00:00.377319+03:00",
    "name": "Интенсив по UX/UI дизайну для команд",
    "event_time": "2026-10-27T17:30:00.376848+03:00",
    "registration_deadline": "2026-10-26T17:30:00.376848+03:00",
    "status": "published",
    "number_of_visitors": 0,
    "status_changed_at": "2026-10-21T00:00:00.400138+03:00",
}


@pytest.fixture
async def http():
    async with httpx.AsyncClient(
        base_url=BASE_URL, headers={"x-api-key": "secret"}
    ) as http_client:
        yield http_client


@pytest.fixture
def client(http: httpx.AsyncClient) -> EventsProviderClient:
    return EventsProviderClient(http)


async def test_get_events_parses_page(client, respx_mock):
    next_url = f"{BASE_URL}/api/events/?changed_at=2000-01-01&cursor=abc123"
    respx_mock.get(f"{BASE_URL}/api/events/").respond(
        200,
        json={"next": next_url, "previous": None, "results": [EVENT_PAYLOAD]},
    )

    page = await client.get_events(date(2000, 1, 1))

    assert isinstance(page, EventsPage)
    assert page.next_cursor == "abc123"
    assert len(page.results) == 1
    event = page.results[0]
    assert event.id == UUID(EVENT_ID)
    assert event.status == "published"
    assert event.place.city == "Владивосток"
    assert event.event_time.utcoffset() is not None


async def test_get_events_last_page_has_no_cursor(client, respx_mock):
    respx_mock.get(f"{BASE_URL}/api/events/").respond(
        200, json={"next": None, "previous": None, "results": []}
    )

    page = await client.get_events(date(2026, 1, 1))

    assert page.results == []
    assert page.next_cursor is None


async def test_get_events_sends_params_and_api_key(client, respx_mock):
    route = respx_mock.get(f"{BASE_URL}/api/events/").respond(
        200, json={"next": None, "previous": None, "results": []}
    )

    await client.get_events(date(2026, 1, 15), cursor="xyz")

    request = route.calls.last.request
    assert request.url.params["changed_at"] == "2026-01-15"
    assert request.url.params["cursor"] == "xyz"
    assert request.headers["x-api-key"] == "secret"


async def test_get_events_unauthorized(client, respx_mock):
    respx_mock.get(f"{BASE_URL}/api/events/").respond(401, json={})

    with pytest.raises(ProviderUnauthorizedError):
        await client.get_events(date(2026, 1, 1))


async def test_get_events_invalid_payload(client, respx_mock):
    respx_mock.get(f"{BASE_URL}/api/events/").respond(
        200, json={"results": [{"id": "not-a-uuid"}]}
    )

    with pytest.raises(ProviderResponseError):
        await client.get_events(date(2026, 1, 1))


async def test_get_events_not_json(client, respx_mock):
    respx_mock.get(f"{BASE_URL}/api/events/").respond(200, text="<html></html>")

    with pytest.raises(ProviderResponseError):
        await client.get_events(date(2026, 1, 1))


async def test_get_events_redirect_is_an_error(client, respx_mock):
    respx_mock.get(f"{BASE_URL}/api/events/").respond(
        301, headers={"Location": "https://provider.test/api/events/"}
    )

    with pytest.raises(ProviderError):
        await client.get_events(date(2026, 1, 1))


async def test_get_events_timeout(client, respx_mock):
    respx_mock.get(f"{BASE_URL}/api/events/").mock(
        side_effect=httpx.ConnectTimeout("timeout")
    )

    with pytest.raises(ProviderUnavailableError):
        await client.get_events(date(2026, 1, 1))


async def test_get_seats_returns_list(client, respx_mock):
    respx_mock.get(f"{BASE_URL}/api/events/{EVENT_ID}/seats/").respond(
        200, json={"seats": ["A1", "B2"]}
    )

    assert await client.get_seats(EVENT_ID) == ["A1", "B2"]


@pytest.mark.parametrize(
    ("status", "expected_error"),
    [
        (400, ProviderBadRequestError),
        (401, ProviderUnauthorizedError),
        (404, ProviderNotFoundError),
        (500, ProviderUnavailableError),
    ],
)
async def test_get_seats_maps_http_errors(client, respx_mock, status, expected_error):
    respx_mock.get(f"{BASE_URL}/api/events/{EVENT_ID}/seats/").respond(
        status, text="<html>error</html>"
    )

    with pytest.raises(expected_error):
        await client.get_seats(EVENT_ID)


async def test_register_returns_ticket_id(client, respx_mock):
    route = respx_mock.post(f"{BASE_URL}/api/events/{EVENT_ID}/register/").respond(
        201, json={"ticket_id": TICKET_ID}
    )

    ticket_id = await client.register(
        EVENT_ID, "Иван", "Иванов", "ivan@example.com", "A15"
    )

    assert ticket_id == TICKET_ID
    assert (
        route.calls.last.request.read()
        == (
            '{"first_name":"Иван","last_name":"Иванов",'
            '"email":"ivan@example.com","seat":"A15"}'
        ).encode()
    )


async def test_register_bad_request(client, respx_mock):
    respx_mock.post(f"{BASE_URL}/api/events/{EVENT_ID}/register/").respond(
        400, json={"detail": "seat is taken"}
    )

    with pytest.raises(ProviderBadRequestError):
        await client.register(EVENT_ID, "Иван", "Иванов", "ivan@example.com", "A15")


async def test_unregister_sends_ticket_id(client, respx_mock):
    route = respx_mock.delete(f"{BASE_URL}/api/events/{EVENT_ID}/unregister/").respond(
        200, json={"success": True}
    )

    result = await client.unregister(EVENT_ID, TICKET_ID)

    assert result is None
    assert TICKET_ID.encode() in route.calls.last.request.read()


async def test_unregister_not_found(client, respx_mock):
    respx_mock.delete(f"{BASE_URL}/api/events/{EVENT_ID}/unregister/").respond(
        404, json={}
    )

    with pytest.raises(ProviderNotFoundError):
        await client.unregister(EVENT_ID, TICKET_ID)
