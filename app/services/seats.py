import logging
import time

from app.clients.events_provider import EventsProviderClient

logger = logging.getLogger(__name__)

CACHE_TTL = 30  # секунд


class SeatsService:
    def __init__(self, client: EventsProviderClient, ttl: float = CACHE_TTL):
        self._client = client
        self._ttl = ttl
        self._cache: dict[str, tuple[float, list[str]]] = {}

    async def get_available_seats(self, event_id: str) -> list[str]:
        now = time.monotonic()
        cached = self._cache.get(event_id)
        if cached and cached[0] > now:
            return cached[1]

        logger.info("Запрос мест у провайдера, event_id=%s", event_id)
        data = await self._client.get_seats(event_id)
        seats = data["seats"]

        self._cache = {k: v for k, v in self._cache.items() if v[0] > now}
        self._cache[event_id] = (now + self._ttl, seats)
        return seats
