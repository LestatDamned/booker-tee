import asyncio
import os
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.base import utc_now
from app.features.chat_integrations.models import TelegramWebhookUpdate
from app.features.chat_integrations.webhook_repository import (
    TelegramWebhookClaimResult,
    TelegramWebhookUpdateRepository,
)

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for Telegram webhook tests.",
)


async def test_telegram_webhook_update_claim_is_persistent_and_concurrency_safe(
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
    update_id = uuid4().int % (2**63 - 1)
    failed_update_id = uuid4().int % (2**63 - 1)
    now = utc_now()

    async def claim() -> TelegramWebhookClaimResult:
        async with sessions() as session:
            return await TelegramWebhookUpdateRepository(session).claim(
                update_id=update_id,
                now=now,
                stale_before=now - timedelta(minutes=5),
            )

    try:
        assert sorted(await asyncio.gather(claim(), claim())) == [
            TelegramWebhookClaimResult.CLAIMED,
            TelegramWebhookClaimResult.IN_PROGRESS,
        ]

        async with sessions() as session:
            await TelegramWebhookUpdateRepository(session).mark_completed(
                update_id=update_id,
                completed_at=utc_now(),
            )

        assert await claim() == TelegramWebhookClaimResult.COMPLETED

        async with sessions() as session:
            failed = TelegramWebhookUpdateRepository(session)
            assert (
                await failed.claim(
                    update_id=failed_update_id,
                    now=now,
                    stale_before=now - timedelta(minutes=5),
                )
                == TelegramWebhookClaimResult.CLAIMED
            )
            await failed.mark_failed(update_id=failed_update_id)
            assert (
                await failed.claim(
                    update_id=failed_update_id,
                    now=utc_now(),
                    stale_before=now - timedelta(minutes=5),
                )
                == TelegramWebhookClaimResult.CLAIMED
            )
    finally:
        async with sessions() as session:
            await session.execute(
                delete(TelegramWebhookUpdate).where(
                    TelegramWebhookUpdate.update_id.in_([update_id, failed_update_id])
                )
            )
            await session.commit()
