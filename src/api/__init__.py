from fastapi import APIRouter

from api.routers import health, sync

router = APIRouter()
router.include_router(health.router)
router.include_router(sync.router)
