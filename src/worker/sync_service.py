import asyncio
import contextlib
import logging
from datetime import timedelta

from domain.exceptions import SyncAlreadyRunningError
from domain.usecases.sync_events import SyncEventsUsecase

logger = logging.getLogger(__name__)


class SyncService:
    """Запускает синхронизацию по расписанию и вручную, в фоне."""

    def __init__(self, usecase: SyncEventsUsecase, interval: timedelta) -> None:
        self._usecase = usecase
        self._interval = interval
        self._periodic_task: asyncio.Task[None] | None = None
        self._manual_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._periodic_task = asyncio.create_task(
            self._periodic_loop(), name="sync-periodic"
        )

    async def stop(self) -> None:
        tasks = [
            task
            for task in (self._periodic_task, self._manual_task)
            if task is not None
        ]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    def is_running(self) -> bool:
        manual_pending = self._manual_task is not None and not self._manual_task.done()
        return self._usecase.is_running or manual_pending

    def trigger(self) -> bool:
        """Запускает синхронизацию в фоне. False, если она уже идёт."""
        if self.is_running():
            return False
        self._manual_task = asyncio.create_task(
            self._run_once("manual"), name="sync-manual"
        )
        return True

    async def _periodic_loop(self) -> None:
        interval_seconds = self._interval.total_seconds()
        while True:
            await self._run_once("scheduled")
            await asyncio.sleep(interval_seconds)

    async def _run_once(self, source: str) -> None:
        try:
            await self._usecase.execute()
        except SyncAlreadyRunningError:
            logger.info("Sync (%s) skipped: already running", source)
        except Exception:
            logger.error("Sync (%s) failed, details are logged above", source)
