import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.events_provider import EventsProviderClient, ProviderError
from app.db.models import Ticket
from app.repositories.events import EventRepository
from app.repositories.tickets import TicketRepository
from app.schemas.tickets import TicketCreate

logger = logging.getLogger(__name__)


class TicketError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _provider_error(e: ProviderError) -> TicketError:
    if e.status_code is not None and 400 <= e.status_code < 500:
        return TicketError(409, "Events provider rejected the request")
    return TicketError(502, "Events provider error")


class TicketService:
    def __init__(self, session: AsyncSession, client: EventsProviderClient):
        self._events = EventRepository(session)
        self._tickets = TicketRepository(session)
        self._client = client

    async def create(self, data: TicketCreate) -> Ticket:
        event = await self._events.get(data.event_id)
        if event is None:
            raise TicketError(404, "Event not found")
        if event.status != "published" or event.registration_deadline <= datetime.now(
            UTC
        ):
            raise TicketError(409, "Registration is closed")

        try:
            result = await self._client.register(
                str(event.id), data.first_name, data.last_name, data.email, data.seat
            )
        except ProviderError as e:
            logger.warning("Регистрация не удалась, event_id=%s: %s", event.id, e)
            raise _provider_error(e) from e

        ticket = Ticket(
            provider_ticket_id=str(result["ticket_id"]),
            event_id=event.id,
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            seat=data.seat,
        )
        ticket = await self._tickets.add(ticket)
        logger.info("Билет создан, ticket_id=%s", ticket.id)
        return ticket

    async def cancel(self, ticket_id: uuid.UUID) -> None:
        ticket = await self._tickets.get(ticket_id)
        if ticket is None:
            raise TicketError(404, "Ticket not found")
        if ticket.status == "cancelled":
            return  # повторная отмена: ничего не делаем

        try:
            result = await self._client.unregister(
                str(ticket.event_id), ticket.provider_ticket_id
            )
        except ProviderError as e:
            logger.warning("Отмена не удалась, ticket_id=%s: %s", ticket.id, e)
            raise _provider_error(e) from e

        if not result.get("success"):
            raise TicketError(502, "Events provider error")

        await self._tickets.mark_cancelled(ticket)
        logger.info("Билет отменён, ticket_id=%s", ticket.id)
