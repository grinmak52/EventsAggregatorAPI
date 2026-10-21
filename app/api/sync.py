from fastapi import APIRouter, BackgroundTasks, Request

from app.db.session import SessionLocal
from app.services.sync import is_sync_running, run_sync

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/trigger")
async def trigger_sync(request: Request, background_tasks: BackgroundTasks):
    if is_sync_running():
        return {"status": "already_running"}
    background_tasks.add_task(run_sync, SessionLocal, request.app.state.provider_client)
    return {"status": "started"}
