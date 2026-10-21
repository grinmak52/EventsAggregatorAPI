import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import Event


class EventRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list(
        self, date_from: date | None, page: int, page_size: int
    ) -> tuple[list[Event], int]:
        conditions = []
        if date_from is not None:
            start = datetime.combine(date_from, time.min, tzinfo=UTC)
            conditions.append(Event.event_time >= start)

        total = await self._session.scalar(
            select(func.count()).select_from(Event).where(*conditions)
        )

        query = (
            select(Event)
            .where(*conditions)
            .options(joinedload(Event.place))
            .order_by(Event.event_time, Event.id)  # id нужен для стабильной сортировки
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self._session.scalars(query)
        return list(result), total or 0

    async def get(self, event_id: uuid.UUID) -> Event | None:
        return await self._session.get(
            Event, event_id, options=[joinedload(Event.place)]
        )
