import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import IdempotencyKey

logger = logging.getLogger(__name__)


async def cleanup_loop(
    session_factory: async_sessionmaker[AsyncSession],
    ttl_seconds: int,
    interval: float,
) -> None:
    while True:
        try:
            cutoff = datetime.now(UTC) - timedelta(seconds=ttl_seconds)
            async with session_factory() as session:
                result = await session.execute(
                    delete(IdempotencyKey).where(IdempotencyKey.created_at < cutoff)
                )
                await session.commit()
            if result.rowcount:
                logger.info("Удалено устаревших ключей: %s", result.rowcount)
        except Exception:
            logger.exception("Ошибка очистки ключей идемпотентности")
        await asyncio.sleep(interval)
