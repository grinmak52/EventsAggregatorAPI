from fastapi import APIRouter

from app.api import events, health, sync, tickets

router = APIRouter(prefix="/api")
router.include_router(health.router)
router.include_router(sync.router)
router.include_router(events.router)
router.include_router(tickets.router)
