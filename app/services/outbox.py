import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import OutboxMessage

logger = logging.getLogger(__name__)


async def _send(message: OutboxMessage) -> None:
    logger.info("Отправка (заглушка): %s %s", message.event_type, message.payload)


async def process_outbox(
    session_factory: async_sessionmaker[AsyncSession],
    batch_size: int,
    max_attempts: int,
) -> None:
    async with session_factory() as session:
        result = await session.execute(
            select(OutboxMessage)
            .where(OutboxMessage.status == "pending")
            .order_by(OutboxMessage.created_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        messages = result.scalars().all()

        for message in messages:
            try:
                await _send(message)
                message.status = "sent"
            except Exception:
                message.attempts += 1
                logger.exception(
                    "Не удалось отправить outbox %s, попытка %s",
                    message.id,
                    message.attempts,
                )
                if message.attempts >= max_attempts:
                    message.status = "failed"
                    logger.error("Outbox %s: попытки закончились", message.id)

        await session.commit()


async def outbox_loop(
    session_factory: async_sessionmaker[AsyncSession],
    interval: float,
    batch_size: int,
    max_attempts: int,
) -> None:
    while True:
        try:
            await process_outbox(session_factory, batch_size, max_attempts)
        except Exception:
            logger.exception("Ошибка в воркере outbox")
        await asyncio.sleep(interval)