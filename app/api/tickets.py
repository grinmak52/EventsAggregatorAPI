import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.tickets import TicketCancelled, TicketCreate, TicketCreated
from app.services.tickets import TicketError, TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


def get_ticket_service(
    request: Request, session: AsyncSession = Depends(get_session)
) -> TicketService:
    return TicketService(session, request.app.state.provider_client)


@router.post("", response_model=TicketCreated, status_code=201)
async def create_ticket(
    data: TicketCreate, service: TicketService = Depends(get_ticket_service)
):
    try:
        ticket = await service.create(data)
    except TicketError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    return TicketCreated(ticket_id=ticket.id)


@router.delete("/{ticket_id}", response_model=TicketCancelled)
async def cancel_ticket(
    ticket_id: uuid.UUID, service: TicketService = Depends(get_ticket_service)
):
    try:
        await service.cancel(ticket_id)
    except TicketError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    return TicketCancelled(success=True)
