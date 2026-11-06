import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.capashino import CapashinoClient, CapashinoError
from app.db.models import OutboxMessage

logger = logging.getLogger(__name__)


async def _send(message: OutboxMessage, client: CapashinoClient) -> None:
    if message.event_type != "ticket_created":
        raise ValueError(f"Неизвестный тип события: {message.event_type}")

    payload = message.payload
    try:
        result = await client.create_notification(
            message=(
                f"Вы успешно зарегистрированы на мероприятие - {payload['event_name']}"
            ),
            reference_id=payload["ticket_id"],
            idempotency_key=str(message.id),
        )
    except CapashinoError as e:
        if e.status_code == 409:
            logger.info("Уведомление уже существует, outbox=%s", message.id)
            return
        raise
    logger.info("Уведомление создано, outbox=%s, id=%s", message.id, result.get("id"))


async def process_outbox(
    session_factory: async_sessionmaker[AsyncSession],
    client: CapashinoClient,
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
                await _send(message, client)
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
    client: CapashinoClient,
    interval: float,
    batch_size: int,
    max_attempts: int,
) -> None:
    while True:
        try:
            await process_outbox(session_factory, client, batch_size, max_attempts)
        except Exception:
            logger.exception("Ошибка в воркере outbox")
        await asyncio.sleep(interval)
