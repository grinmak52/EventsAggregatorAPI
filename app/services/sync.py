import asyncio
import logging
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.events_provider import EventsProviderClient
from app.clients.paginator import EventsPaginator
from app.db.models import Event, Place, SyncMetadata

logger = logging.getLogger(__name__)

FIRST_SYNC_DATE = date(2000, 1, 1)
OVERLAP = timedelta(days=1)

_lock = asyncio.Lock()


def is_sync_running() -> bool:
    return _lock.locked()


async def _get_metadata(session: AsyncSession) -> SyncMetadata:
    meta = await session.get(SyncMetadata, 1)
    if meta is None:
        meta = SyncMetadata(id=1, sync_status="idle")
        session.add(meta)
        await session.flush()
    return meta


async def _upsert(session: AsyncSession, model, values: dict) -> None:
    stmt = insert(model).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={k: v for k, v in values.items() if k != "id"},
    )
    await session.execute(stmt)


def _place_values(place: dict) -> dict:
    return {
        "id": uuid.UUID(place["id"]),
        "name": place["name"],
        "city": place.get("city"),
        "address": place.get("address"),
        "seats_pattern": place.get("seats_pattern"),
    }


def _event_values(event: dict) -> dict:
    return {
        "id": uuid.UUID(event["id"]),
        "name": event["name"],
        "place_id": uuid.UUID(event["place"]["id"]),
        "event_time": datetime.fromisoformat(event["event_time"]),
        "registration_deadline": datetime.fromisoformat(event["registration_deadline"]),
        "status": event["status"],
        "number_of_visitors": event["number_of_visitors"],
        "changed_at": datetime.fromisoformat(event["changed_at"]),
    }


async def run_sync(
    session_factory: async_sessionmaker[AsyncSession],
    client: EventsProviderClient,
) -> bool:
    """Запускает синхронизацию. Возвращает False, если она уже идёт."""
    if _lock.locked():
        return False

    async with _lock:
        async with session_factory() as session:
            meta = await _get_metadata(session)
            if meta.last_changed_at is None:
                since = FIRST_SYNC_DATE
            else:
                since = (meta.last_changed_at - OVERLAP).date()
            meta.sync_status = "running"
            await session.commit()

        logger.info("Синхронизация началась, changed_at=%s", since)

        # 2. Загружаем и сохраняем данные одной транзакцией
        try:
            async with session_factory() as session:
                count = 0
                max_changed = None
                async for item in EventsPaginator(client, since):
                    event_values = _event_values(item)
                    await _upsert(session, Place, _place_values(item["place"]))
                    await _upsert(session, Event, event_values)
                    count += 1
                    changed = event_values["changed_at"]
                    if max_changed is None or changed > max_changed:
                        max_changed = changed

                meta = await _get_metadata(session)
                meta.sync_status = "idle"
                meta.last_sync_time = datetime.now(UTC)
                if max_changed and (
                    meta.last_changed_at is None or max_changed > meta.last_changed_at
                ):
                    meta.last_changed_at = max_changed
                await session.commit()
            logger.info("Синхронизация завершена, обработано: %s", count)
        except Exception:
            logger.exception("Синхронизация не удалась")
            async with session_factory() as session:
                meta = await _get_metadata(session)
                meta.sync_status = "failed"
                await session.commit()

        return True


async def sync_loop(
    session_factory: async_sessionmaker[AsyncSession],
    client: EventsProviderClient,
    interval: float,
) -> None:
    while True:
        try:
            await run_sync(session_factory, client)
        except Exception:
            logger.exception("Ошибка в фоновой синхронизации")
        await asyncio.sleep(interval)
