import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from domain.entities import Event, SyncMetadata, SyncStatus
from domain.exceptions import SyncAlreadyRunningError
from domain.repositories import EventRepository, SyncMetadataRepository

logger = logging.getLogger(__name__)

INITIAL_CHANGED_AT = date(2000, 1, 1)
SAFETY_WINDOW = timedelta(days=1)
MAX_ERROR_LENGTH = 1000

EventsSource = Callable[[date], AsyncIterator[Event]]


@dataclass(frozen=True, slots=True)
class SyncResult:
    processed: int
    last_changed_at: datetime | None


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _start_date(last_changed_at: datetime | None) -> date:
    if last_changed_at is None:
        return INITIAL_CHANGED_AT
    return (last_changed_at - SAFETY_WINDOW).date()


class SyncEventsUsecase:
    def __init__(
        self,
        events_source: EventsSource,
        event_repo: EventRepository,
        metadata_repo: SyncMetadataRepository,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._events_source = events_source
        self._event_repo = event_repo
        self._metadata_repo = metadata_repo
        self._now = now
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._lock.locked()

    async def execute(self) -> SyncResult:
        if self.is_running:
            raise SyncAlreadyRunningError("Synchronization is already running")
        async with self._lock:
            return await self._run()

    async def _run(self) -> SyncResult:
        started_at = self._now()
        previous = await self._metadata_repo.get()
        previous_changed_at = previous.last_changed_at if previous else None
        changed_at = _start_date(previous_changed_at)

        logger.info("Sync started: changed_at=%s", changed_at)
        await self._metadata_repo.update(
            SyncMetadata(
                last_sync_time=started_at,
                last_changed_at=previous_changed_at,
                sync_status=SyncStatus.RUNNING,
                error_message=None,
            )
        )

        processed = 0
        max_changed_at = previous_changed_at
        try:
            async for event in self._events_source(changed_at):
                await self._event_repo.upsert(event)
                processed += 1
                if max_changed_at is None or event.changed_at > max_changed_at:
                    max_changed_at = event.changed_at
        except Exception as exc:
            logger.exception("Sync failed after %s events", processed)
            await self._mark_failed(started_at, previous_changed_at, exc)
            raise

        await self._metadata_repo.update(
            SyncMetadata(
                last_sync_time=started_at,
                last_changed_at=max_changed_at,
                sync_status=SyncStatus.IDLE,
                error_message=None,
            )
        )
        logger.info(
            "Sync finished: processed=%s last_changed_at=%s",
            processed,
            max_changed_at,
        )
        return SyncResult(processed=processed, last_changed_at=max_changed_at)

    async def _mark_failed(
        self,
        started_at: datetime,
        last_changed_at: datetime | None,
        exc: Exception,
    ) -> None:
        message = f"{type(exc).__name__}: {exc}"[:MAX_ERROR_LENGTH]
        try:
            await self._metadata_repo.update(
                SyncMetadata(
                    last_sync_time=started_at,
                    last_changed_at=last_changed_at,
                    sync_status=SyncStatus.FAILED,
                    error_message=message,
                )
            )
        except Exception:
            logger.exception("Could not record sync failure")
