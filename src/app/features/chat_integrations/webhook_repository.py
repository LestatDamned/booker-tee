from datetime import datetime
from enum import StrEnum

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.chat_integrations.models import TelegramWebhookUpdate

PROCESSING = "processing"
COMPLETED = "completed"
FAILED = "failed"


class TelegramWebhookClaimResult(StrEnum):
    CLAIMED = "claimed"
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"


class TelegramWebhookUpdateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim(
        self,
        *,
        update_id: int,
        now: datetime,
        stale_before: datetime,
    ) -> TelegramWebhookClaimResult:
        inserted = await self.session.execute(
            insert(TelegramWebhookUpdate)
            .values(
                update_id=update_id,
                status=PROCESSING,
                attempt_count=1,
                started_at=now,
                created_at=now,
            )
            .on_conflict_do_nothing(index_elements=[TelegramWebhookUpdate.update_id])
            .returning(TelegramWebhookUpdate.update_id)
        )
        if inserted.scalar_one_or_none() is not None:
            await self.session.commit()
            return TelegramWebhookClaimResult.CLAIMED

        stored = await self.session.scalar(
            select(TelegramWebhookUpdate)
            .where(TelegramWebhookUpdate.update_id == update_id)
            .with_for_update()
        )
        if stored is None:
            await self.session.rollback()
            return TelegramWebhookClaimResult.IN_PROGRESS
        if stored.status == COMPLETED:
            await self.session.commit()
            return TelegramWebhookClaimResult.COMPLETED
        if stored.status == PROCESSING and stored.started_at > stale_before:
            await self.session.commit()
            return TelegramWebhookClaimResult.IN_PROGRESS

        stored.status = PROCESSING
        stored.attempt_count += 1
        stored.started_at = now
        await self.session.commit()
        return TelegramWebhookClaimResult.CLAIMED

    async def mark_completed(self, *, update_id: int, completed_at: datetime) -> None:
        await self.session.execute(
            update(TelegramWebhookUpdate)
            .where(TelegramWebhookUpdate.update_id == update_id)
            .values(status=COMPLETED, completed_at=completed_at)
        )
        await self.session.commit()

    async def mark_failed(self, *, update_id: int) -> None:
        await self.session.rollback()
        await self.session.execute(
            update(TelegramWebhookUpdate)
            .where(TelegramWebhookUpdate.update_id == update_id)
            .values(status=FAILED)
        )
        await self.session.commit()
