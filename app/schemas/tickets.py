import uuid

from pydantic import BaseModel, EmailStr, Field


class TicketCreate(BaseModel):
    event_id: uuid.UUID
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    seat: str = Field(min_length=1, max_length=20)


class TicketCreated(BaseModel):
    ticket_id: uuid.UUID


class TicketCancelled(BaseModel):
    success: bool
