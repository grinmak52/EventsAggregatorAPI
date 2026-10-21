import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlaceShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    city: str | None
    address: str | None


class PlaceDetail(PlaceShort):
    seats_pattern: str | None


class EventShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    place: PlaceShort
    event_time: datetime
    registration_deadline: datetime
    status: str
    number_of_visitors: int


class EventDetail(EventShort):
    place: PlaceDetail


class EventList(BaseModel):
    count: int
    next: str | None
    previous: str | None
    results: list[EventShort]


class SeatsOut(BaseModel):
    event_id: uuid.UUID
    available_seats: list[str]
