from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OutboxMessage


class OutboxRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, event_type: str, payload: dict) -> OutboxMessage:
        message = OutboxMessage(event_type=event_type, payload=payload)
        self._session.add(message)
        return message
