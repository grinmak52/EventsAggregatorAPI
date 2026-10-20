import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime

import pytest

from domain.entities import Event, SyncMetadata, SyncStatus
from domain.exceptions import ProviderUnavailableError, SyncAlreadyRunningError
from domain.usecases.sync_events import SyncEventsUsecase
from tests.factories import make_event

FIXED_NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


class FakeEventRepository:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def upsert(self, event: Event) -> None:
        self.events.append(event)


class FakeMetadataRepository:
    def __init__(self, initial: SyncMetadata | None = None) -> None:
        self.current = initial
        self.history: list[SyncMetadata] = []

    async def get(self) -> SyncMetadata | None:
        return self.current

    async def update(self, metadata: SyncMetadata) -> None:
        self.current = metadata
        self.history.append(metadata)


class FakeSource:
    def __init__(self, events: list[Event], error: Exception | None = None) -> None:
        self.events = events
        self.error = error
        self.calls: list[date] = []

    async def __call__(self, changed_at: date) -> AsyncIterator[Event]:
        self.calls.append(changed_at)
        for event in self.events:
            yield event
        if self.error is not None:
            raise self.error


def make_usecase(source, metadata: SyncMetadata | None = None):
    event_repo = FakeEventRepository()
    metadata_repo = FakeMetadataRepository(metadata)
    usecase = SyncEventsUsecase(
        source, event_repo, metadata_repo, now=lambda: FIXED_NOW
    )
    return usecase, event_repo, metadata_repo


def previous_metadata(last_changed_at: datetime) -> SyncMetadata:
    return SyncMetadata(
        last_sync_time=FIXED_NOW,
        last_changed_at=last_changed_at,
        sync_status=SyncStatus.IDLE,
        error_message=None,
    )


async def test_first_sync_starts_from_2000_and_saves_max_changed_at():
    events = [
        make_event("a", datetime(2026, 10, 20, 10, tzinfo=UTC)),
        make_event("b", datetime(2026, 10, 21, 0, tzinfo=UTC)),
        make_event("c", datetime(2026, 10, 20, 12, tzinfo=UTC)),
    ]
    source = FakeSource(events)
    usecase, event_repo, metadata_repo = make_usecase(source)

    result = await usecase.execute()

    assert source.calls == [date(2000, 1, 1)]
    assert event_repo.events == events
    assert result.processed == 3
    assert result.last_changed_at == datetime(2026, 10, 21, 0, tzinfo=UTC)
    assert metadata_repo.current == SyncMetadata(
        last_sync_time=FIXED_NOW,
        last_changed_at=datetime(2026, 10, 21, 0, tzinfo=UTC),
        sync_status=SyncStatus.IDLE,
        error_message=None,
    )


async def test_next_sync_starts_one_day_before_last_changed_at():
    source = FakeSource([])
    metadata = previous_metadata(datetime(2026, 10, 20, 21, 0, tzinfo=UTC))
    usecase, _, _ = make_usecase(source, metadata)

    await usecase.execute()

    assert source.calls == [date(2026, 10, 19)]


async def test_sync_without_events_keeps_last_changed_at():
    last_changed_at = datetime(2026, 10, 20, 21, 0, tzinfo=UTC)
    usecase, _, metadata_repo = make_usecase(
        FakeSource([]), previous_metadata(last_changed_at)
    )

    result = await usecase.execute()

    assert result.processed == 0
    assert metadata_repo.current.last_changed_at == last_changed_at
    assert metadata_repo.current.sync_status == SyncStatus.IDLE


async def test_status_goes_running_then_idle():
    usecase, _, metadata_repo = make_usecase(FakeSource([make_event()]))

    await usecase.execute()

    statuses = [m.sync_status for m in metadata_repo.history]
    assert statuses == [SyncStatus.RUNNING, SyncStatus.IDLE]


async def test_failure_is_recorded_and_reraised():
    last_changed_at = datetime(2026, 10, 20, 21, 0, tzinfo=UTC)
    source = FakeSource(
        [make_event("a", datetime(2026, 10, 21, tzinfo=UTC))],
        error=ProviderUnavailableError("down"),
    )
    usecase, event_repo, metadata_repo = make_usecase(
        source, previous_metadata(last_changed_at)
    )

    with pytest.raises(ProviderUnavailableError):
        await usecase.execute()

    assert len(event_repo.events) == 1
    final = metadata_repo.current
    assert final.sync_status == SyncStatus.FAILED
    assert "down" in final.error_message
    assert final.last_changed_at == last_changed_at


async def test_retry_after_failure_is_allowed():
    source = FakeSource([make_event()], error=ProviderUnavailableError("down"))
    usecase, _, metadata_repo = make_usecase(source)

    with pytest.raises(ProviderUnavailableError):
        await usecase.execute()
    source.error = None
    result = await usecase.execute()

    assert result.processed == 1
    assert metadata_repo.current.sync_status == SyncStatus.IDLE
    assert metadata_repo.current.error_message is None


async def test_concurrent_run_is_rejected():
    gate = asyncio.Event()

    async def blocking_source(changed_at: date) -> AsyncIterator[Event]:
        await gate.wait()
        for event in ():
            yield event

    usecase, _, _ = make_usecase(blocking_source)

    first = asyncio.create_task(usecase.execute())
    await asyncio.sleep(0)

    with pytest.raises(SyncAlreadyRunningError):
        await usecase.execute()

    gate.set()
    result = await first
    assert result.processed == 0
