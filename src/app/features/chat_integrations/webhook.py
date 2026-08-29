import asyncio
import secrets
from datetime import timedelta

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.base import utc_now
from app.features.chat_integrations.providers.telegram import TelegramUpdateNormalizer
from app.features.chat_integrations.providers.telegram_client import (
    TelegramBotClient,
    TelegramOutboundMessageSender,
    create_telegram_http_client,
)
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.service import ChatEventService
from app.features.chat_integrations.webhook_repository import (
    TelegramWebhookClaimResult,
    TelegramWebhookUpdateRepository,
)

TELEGRAM_WEBHOOK_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"
TELEGRAM_WEBHOOK_PATH = "/chat-integrations/telegram/webhook"
TELEGRAM_WEBHOOK_PROCESSING_LEASE = timedelta(minutes=5)


class TelegramWebhookRuntimePolicy:
    @staticmethod
    def require_webhook_mode(settings: Settings) -> None:
        if not settings.chat_integrations_enabled:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        if settings.telegram_mode != "webhook":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        if settings.telegram_bot_token is None or settings.telegram_webhook_secret is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


class TelegramWebhookSecretPolicy:
    @staticmethod
    def require_valid_secret(*, settings: Settings, received_secret: str | None) -> None:
        TelegramWebhookRuntimePolicy.require_webhook_mode(settings)
        expected_secret = settings.telegram_webhook_secret or ""
        if not secrets.compare_digest(received_secret or "", expected_secret):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


class TelegramWebhookUrlBuilder:
    @staticmethod
    def build_public_webhook_url(settings: Settings) -> str:
        base_url = settings.telegram_webhook_base_url or settings.public_base_url
        if base_url is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return f"{base_url.rstrip('/')}{TELEGRAM_WEBHOOK_PATH}"


class TelegramWebhookRegistrar:
    def __init__(self, *, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def register_webhook(self, *, drop_pending_updates: bool = False) -> str:
        TelegramWebhookRuntimePolicy.require_webhook_mode(self.settings)
        webhook_url = TelegramWebhookUrlBuilder.build_public_webhook_url(self.settings)
        client = TelegramBotClient(
            bot_token=TelegramWebhookSettingsReader.require_bot_token(self.settings),
            http_client=self.http_client,
            download_max_bytes=self.settings.statement_upload_max_bytes,
        )
        await client.set_webhook(
            url=webhook_url,
            secret_token=TelegramWebhookSettingsReader.require_webhook_secret(self.settings),
            ip_address=(
                str(self.settings.telegram_webhook_ip_address)
                if self.settings.telegram_webhook_ip_address
                else None
            ),
            drop_pending_updates=drop_pending_updates,
        )
        return webhook_url


class TelegramWebhookUpdateReceiver:
    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.session = session
        self.settings = settings
        self.http_client = http_client
        self.updates = TelegramWebhookUpdateRepository(session)

    async def receive_update(self, update: dict[str, object]) -> bool:
        update_id = TelegramWebhookUpdateIdReader.require(update)
        now = utc_now()
        claim = await self.updates.claim(
            update_id=update_id,
            now=now,
            stale_before=now - TELEGRAM_WEBHOOK_PROCESSING_LEASE,
        )
        if claim == TelegramWebhookClaimResult.COMPLETED:
            return False
        if claim == TelegramWebhookClaimResult.IN_PROGRESS:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Telegram update is already being processed.",
            )

        client = TelegramBotClient(
            bot_token=TelegramWebhookSettingsReader.require_bot_token(self.settings),
            http_client=self.http_client,
            download_max_bytes=self.settings.statement_upload_max_bytes,
        )
        try:
            event = TelegramWebhookUpdateNormalizer.normalize_update(update)
            response = await ChatEventService(
                self.session,
                self.settings,
                client,
                client,
            ).receive_inbound_event(event)
            await TelegramWebhookResponseSender.send_response(client, event, response)
        except Exception:
            await self.updates.mark_failed(update_id=update_id)
            raise
        await self.updates.mark_completed(update_id=update_id, completed_at=utc_now())
        return True


class TelegramWebhookUpdateIdReader:
    @staticmethod
    def require(update: dict[str, object]) -> int:
        update_id = update.get("update_id")
        if not isinstance(update_id, int) or isinstance(update_id, bool) or update_id < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Telegram update_id is required.",
            )
        return update_id


class TelegramWebhookUpdateNormalizer:
    @staticmethod
    def normalize_update(update: dict[str, object]) -> InboundChatEvent:
        return TelegramUpdateNormalizer.normalize_update(update)


class TelegramWebhookResponseSender:
    @staticmethod
    async def send_response(
        client: TelegramBotClient,
        event: InboundChatEvent,
        response: OutboundChatMessage | None,
    ) -> None:
        await TelegramOutboundMessageSender.send_response(
            client=client,
            event=event,
            response=response,
        )


class TelegramWebhookSettingsReader:
    @staticmethod
    def require_bot_token(settings: Settings) -> str:
        if settings.telegram_bot_token is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return settings.telegram_bot_token

    @staticmethod
    def require_webhook_secret(settings: Settings) -> str:
        if settings.telegram_webhook_secret is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return settings.telegram_webhook_secret


async def register_telegram_webhook_from_settings() -> str:
    settings = get_settings()
    settings.validate_for_runtime()
    async with create_telegram_http_client(settings) as client:
        return await TelegramWebhookRegistrar(
            settings=settings,
            http_client=client,
        ).register_webhook()


def main() -> None:
    webhook_url = asyncio.run(register_telegram_webhook_from_settings())
    print(f"Telegram webhook registered: {webhook_url}")


if __name__ == "__main__":
    main()
