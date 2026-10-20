from typing import Protocol

from domain.entities import Event, SyncMetadata


class EventRepository(Protocol):
    async def upsert(self, event: Event) -> None: ...


class SyncMetadataRepository(Protocol):
    async def get(self) -> SyncMetadata | None: ...

    async def update(self, metadata: SyncMetadata) -> None: ...
