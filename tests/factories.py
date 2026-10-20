from datetime import UTC, datetime
from uuid import uuid4

from domain.entities import Event, Place


def make_event(name: str = "event", changed_at: datetime | None = None) -> Event:
    changed_at = changed_at or datetime(2026, 10, 21, tzinfo=UTC)
    place = Place(
        id=uuid4(),
        name="Place",
        city="Moscow",
        address="Address",
        seats_pattern="A1-10",
        created_at=changed_at,
        changed_at=changed_at,
    )
    return Event(
        id=uuid4(),
        name=name,
        place=place,
        event_time=changed_at,
        registration_deadline=changed_at,
        status="published",
        number_of_visitors=0,
        created_at=changed_at,
        changed_at=changed_at,
        status_changed_at=None,
    )
