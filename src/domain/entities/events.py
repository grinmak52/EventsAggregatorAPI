from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Place:
    id: UUID
    name: str
    city: str
    address: str
    seats_pattern: str
    created_at: datetime
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class Event:
    id: UUID
    name: str
    place: Place
    event_time: datetime
    registration_deadline: datetime
    status: str
    number_of_visitors: int
    created_at: datetime
    changed_at: datetime
    status_changed_at: datetime | None


@dataclass(frozen=True, slots=True)
class EventsPage:
    results: list[Event]
    next_cursor: str | None
