import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.providers.telegram import TelegramUpdateNormalizer
from app.features.chat_integrations.providers.telegram_client import (
    TelegramBotClient,
    TelegramOutboundMessageSender,
)
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.service import ChatEventService

TELEGRAM_WEBHOOK_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"
TELEGRAM_WEBHOOK_PATH = "/chat-integrations/telegram/webhook"


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
        if received_secret != settings.telegram_webhook_secret:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


class TelegramWebhookUrlBuilder:
    @staticmethod
    def build_public_webhook_url(settings: Settings) -> str:
        if settings.public_base_url is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return f"{settings.public_base_url.rstrip('/')}{TELEGRAM_WEBHOOK_PATH}"


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
        )
        await client.set_webhook(
            url=webhook_url,
            secret_token=TelegramWebhookSettingsReader.require_webhook_secret(self.settings),
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

    async def receive_update(self, update: dict[str, object]) -> None:
        client = TelegramBotClient(
            bot_token=TelegramWebhookSettingsReader.require_bot_token(self.settings),
            http_client=self.http_client,
        )
        event = TelegramWebhookUpdateNormalizer.normalize_update(update)
        response = await ChatEventService(
            self.session,
            self.settings,
            client,
            client,
        ).receive_inbound_event(event)
        await TelegramWebhookResponseSender.send_response(client, event, response)


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
