import asyncio
from datetime import timedelta

from domain.exceptions import ProviderUnavailableError
from worker.sync_service import SyncService


class FakeUsecase:
    def __init__(self, behavior=None) -> None:
        self.calls = 0
        self.is_running = False
        self.behavior = behavior

    async def execute(self) -> None:
        self.calls += 1
        if self.behavior is not None:
            await self.behavior()


def make_service(usecase, interval=timedelta(hours=24)) -> SyncService:
    return SyncService(usecase, interval=interval)


async def test_trigger_runs_sync_in_background():
    usecase = FakeUsecase()
    service = make_service(usecase)

    assert service.trigger() is True
    await asyncio.sleep(0)

    assert usecase.calls == 1


async def test_trigger_is_rejected_while_running():
    gate = asyncio.Event()
    usecase = FakeUsecase(behavior=gate.wait)
    service = make_service(usecase)

    assert service.trigger() is True
    await asyncio.sleep(0)
    assert service.trigger() is False
    assert usecase.calls == 1

    gate.set()
    await asyncio.sleep(0.01)
    assert service.trigger() is True


async def test_failed_sync_does_not_break_service():
    failed = asyncio.Event()

    async def fail():
        failed.set()
        raise ProviderUnavailableError("down")

    usecase = FakeUsecase(behavior=fail)
    service = make_service(usecase)

    assert service.trigger() is True
    await asyncio.wait_for(failed.wait(), timeout=1)
    await asyncio.sleep(0.01)

    assert service.trigger() is True


async def test_periodic_loop_repeats_and_survives_errors():
    reached = asyncio.Event()
    usecase = FakeUsecase()

    async def flaky():
        if usecase.calls == 1:
            raise ProviderUnavailableError("down")
        if usecase.calls >= 3:
            reached.set()

    usecase.behavior = flaky
    service = make_service(usecase, interval=timedelta(milliseconds=5))

    service.start()
    await asyncio.wait_for(reached.wait(), timeout=2)
    await service.stop()

    assert usecase.calls >= 3


async def test_stop_cancels_running_sync():
    gate = asyncio.Event()
    usecase = FakeUsecase(behavior=gate.wait)
    service = make_service(usecase)

    service.trigger()
    await asyncio.sleep(0)

    await asyncio.wait_for(service.stop(), timeout=1)
