import logging
from contextlib import asynccontextmanager
from datetime import timedelta

import uvicorn
from fastapi import FastAPI

from api import router as api_router
from core.config import settings
from domain.usecases.sync_events import SyncEventsUsecase
from infrastructure.clients.events_provider import (
    EventsProviderClient,
    create_http_client,
)
from infrastructure.db import db_helper
from infrastructure.db.repositories import (
    SqlAlchemyEventRepository,
    SqlAlchemySyncMetadataRepository,
)
from worker.paginator import EventsPaginator
from worker.sync_service import SyncService

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    http_client = create_http_client(settings.events_provider)
    provider = EventsProviderClient(http_client)
    usecase = SyncEventsUsecase(
        events_source=lambda changed_at: EventsPaginator(provider, changed_at),
        event_repo=SqlAlchemyEventRepository(db_helper.session_factory),
        metadata_repo=SqlAlchemySyncMetadataRepository(db_helper.session_factory),
    )
    sync_service = SyncService(
        usecase, interval=timedelta(hours=settings.sync.interval_hours)
    )
    app.state.sync_service = sync_service
    if settings.sync.enabled:
        sync_service.start()

    yield

    await sync_service.stop()
    await http_client.aclose()
    await db_helper.dispose()


main_app = FastAPI(lifespan=lifespan)
main_app.include_router(
    api_router,
    prefix=settings.api.prefix,
)

if __name__ == "__main__":
    uvicorn.run(
        "main:main_app",
        host=settings.run.host,
        port=settings.run.port,
        reload=True,
    )
