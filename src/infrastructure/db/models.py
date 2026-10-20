import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.base import Base


class Place(Base):
    __tablename__ = "places"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str]
    city: Mapped[str]
    address: Mapped[str]
    seats_pattern: Mapped[str]
    created_at: Mapped[datetime]
    changed_at: Mapped[datetime]


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str]
    place_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("places.id"))
    event_time: Mapped[datetime] = mapped_column(index=True)
    registration_deadline: Mapped[datetime]
    status: Mapped[str] = mapped_column(index=True)
    number_of_visitors: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime]
    changed_at: Mapped[datetime] = mapped_column(index=True)
    status_changed_at: Mapped[datetime | None]

    place: Mapped[Place] = relationship(lazy="joined")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    first_name: Mapped[str]
    last_name: Mapped[str]
    email: Mapped[str]
    seat: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    cancelled_at: Mapped[datetime | None]


class SyncMetadata(Base):
    __tablename__ = "sync_metadata"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False, default=1)
    last_sync_time: Mapped[datetime | None]
    last_changed_at: Mapped[datetime | None]
    sync_status: Mapped[str] = mapped_column(default="idle", server_default="idle")
    error_message: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
