from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.entities import Event, SyncMetadata, SyncStatus
from infrastructure.db import models

SessionFactory = async_sessionmaker[AsyncSession]

SYNC_METADATA_ROW_ID = 1


def _build_upsert(model: type[models.Place | models.Event], values: dict[str, Any]):
    stmt = insert(model).values(**values)
    return stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={key: stmt.excluded[key] for key in values if key != "id"},
        where=model.changed_at <= stmt.excluded.changed_at,
    )


class SqlAlchemyEventRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def upsert(self, event: Event) -> None:
        place = event.place
        place_values = {
            "id": place.id,
            "name": place.name,
            "city": place.city,
            "address": place.address,
            "seats_pattern": place.seats_pattern,
            "created_at": place.created_at,
            "changed_at": place.changed_at,
        }
        event_values = {
            "id": event.id,
            "name": event.name,
            "place_id": place.id,
            "event_time": event.event_time,
            "registration_deadline": event.registration_deadline,
            "status": event.status,
            "number_of_visitors": event.number_of_visitors,
            "created_at": event.created_at,
            "changed_at": event.changed_at,
            "status_changed_at": event.status_changed_at,
        }
        async with self._session_factory() as session, session.begin():
            await session.execute(_build_upsert(models.Place, place_values))
            await session.execute(_build_upsert(models.Event, event_values))


class SqlAlchemySyncMetadataRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def get(self) -> SyncMetadata | None:
        async with self._session_factory() as session:
            row = await session.get(models.SyncMetadata, SYNC_METADATA_ROW_ID)
        if row is None:
            return None
        return SyncMetadata(
            last_sync_time=row.last_sync_time,
            last_changed_at=row.last_changed_at,
            sync_status=SyncStatus(row.sync_status),
            error_message=row.error_message,
        )

    async def update(self, metadata: SyncMetadata) -> None:
        values = {
            "id": SYNC_METADATA_ROW_ID,
            "last_sync_time": metadata.last_sync_time,
            "last_changed_at": metadata.last_changed_at,
            "sync_status": metadata.sync_status.value,
            "error_message": metadata.error_message,
        }
        stmt = insert(models.SyncMetadata).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                **{key: stmt.excluded[key] for key in values if key != "id"},
                "updated_at": func.now(),
            },
        )
        async with self._session_factory() as session, session.begin():
            await session.execute(stmt)
