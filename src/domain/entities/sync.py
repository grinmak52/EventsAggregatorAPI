from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SyncStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SyncMetadata:
    last_sync_time: datetime | None
    last_changed_at: datetime | None
    sync_status: SyncStatus
    error_message: str | None
