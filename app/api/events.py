import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.events_provider import ProviderError
from app.db.session import get_session
from app.repositories.events import EventRepository
from app.schemas.events import EventDetail, EventList, SeatsOut

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=EventList)
async def list_events(
    request: Request,
    date_from: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    events, count = await EventRepository(session).list(date_from, page, page_size)

    next_url = None
    if page * page_size < count:
        next_url = str(request.url.include_query_params(page=page + 1))
    previous_url = None
    if page > 1:
        previous_url = str(request.url.include_query_params(page=page - 1))

    return EventList(count=count, next=next_url, previous=previous_url, results=events)


@router.get("/{event_id}", response_model=EventDetail)
async def get_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    event = await EventRepository(session).get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/{event_id}/seats", response_model=SeatsOut)
async def get_event_seats(
    event_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    event = await EventRepository(session).get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    try:
        seats = await request.app.state.seats_service.get_available_seats(str(event_id))
    except ProviderError as e:
        if e.status_code is not None and 400 <= e.status_code < 500:
            # например, мероприятие не опубликовано
            raise HTTPException(
                status_code=409, detail="Seats are not available for this event"
            ) from e
        raise HTTPException(status_code=502, detail="Events provider error") from e

    return SeatsOut(event_id=event_id, available_seats=seats)
