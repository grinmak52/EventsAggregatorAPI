from fastapi import Request

from worker.sync_service import SyncService


def get_sync_service(request: Request) -> SyncService:
    return request.app.state.sync_service
