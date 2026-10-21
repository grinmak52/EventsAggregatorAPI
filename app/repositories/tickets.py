import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ticket


class TicketRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, ticket: Ticket) -> Ticket:
        self._session.add(ticket)
        await self._session.commit()
        return ticket

    async def get(self, ticket_id: uuid.UUID) -> Ticket | None:
        return await self._session.get(Ticket, ticket_id)

    async def mark_cancelled(self, ticket: Ticket) -> None:
        ticket.status = "cancelled"
        ticket.cancelled_at = datetime.now(UTC)
        await self._session.commit()
