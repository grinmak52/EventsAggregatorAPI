import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import api
from app.clients.events_provider import EventsProviderClient
from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.services.seats import SeatsService
from app.services.sync import sync_loop

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.provider_client = EventsProviderClient(
        settings.provider_url, settings.provider_api_key
    )
    app.state.seats_service = SeatsService(app.state.provider_client)

    sync_task = asyncio.create_task(
        sync_loop(
            SessionLocal,
            app.state.provider_client,
            settings.sync_interval_seconds,
        )
    )
    yield

    sync_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await sync_task
    await app.state.provider_client.close()
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(api.router)
