from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_sync_service
from worker.sync_service import SyncService

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/trigger")
async def trigger_sync(
    service: Annotated[SyncService, Depends(get_sync_service)],
) -> dict[str, str]:
    if service.trigger():
        return {"status": "started", "message": "Synchronization triggered"}
    return {
        "status": "already_running",
        "message": "Synchronization is already running",
    }
