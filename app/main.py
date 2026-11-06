import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app import api
from app.clients.capashino import CapashinoClient
from app.clients.events_provider import EventsProviderClient
from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.services.idempotency import cleanup_loop
from app.services.outbox import outbox_loop
from app.services.seats import SeatsService
from app.services.sync import sync_loop

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.provider_client = EventsProviderClient(
        settings.provider_url, settings.provider_api_key
    )
    app.state.seats_service = SeatsService(app.state.provider_client)
    app.state.capashino_client = CapashinoClient(
        settings.capashino_url, settings.capashino_api_key
    )

    sync_task = asyncio.create_task(
        sync_loop(
            SessionLocal,
            app.state.provider_client,
            settings.sync_interval_seconds,
        )
    )
    outbox_task = asyncio.create_task(
        outbox_loop(
            SessionLocal,
            app.state.capashino_client,
            settings.outbox_interval_seconds,
            settings.outbox_batch_size,
            settings.outbox_max_attempts,
        )
    )
    cleanup_task = asyncio.create_task(
        cleanup_loop(
            SessionLocal,
            settings.idempotency_ttl_seconds,
            settings.idempotency_cleanup_interval_seconds,
        )
    )
    yield
    tasks = [sync_task, outbox_task, cleanup_task]
    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await app.state.provider_client.close()
    await app.state.capashino_client.close()
    await engine.dispose()


if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[FastApiIntegration()],
    )

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(api.router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=400, content={"detail": errors})
