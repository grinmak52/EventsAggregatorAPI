import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IdempotencyKey


class IdempotencyRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, key: str) -> IdempotencyKey | None:
        return await self._session.get(IdempotencyKey, key)

    async def add(self, key: str, ticket_id: uuid.UUID) -> None:
        self._session.add(IdempotencyKey(key=key, ticket_id=ticket_id))
