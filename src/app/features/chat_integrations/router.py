from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.chat_integrations.providers.telegram_client import (
    create_telegram_http_client,
)
from app.features.chat_integrations.webhook import (
    TELEGRAM_WEBHOOK_SECRET_HEADER,
    TelegramWebhookSecretPolicy,
    TelegramWebhookUpdateReceiver,
)

router = APIRouter(prefix="/chat-integrations", tags=["chat-integrations"])


@router.post("/telegram/webhook")
async def telegram_webhook(
    update: dict[str, object],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    telegram_secret: Annotated[
        str | None,
        Header(alias=TELEGRAM_WEBHOOK_SECRET_HEADER),
    ] = None,
) -> dict[str, bool]:
    TelegramWebhookSecretPolicy.require_valid_secret(
        settings=settings,
        received_secret=telegram_secret,
    )
    async with create_telegram_http_client(settings) as client:
        await TelegramWebhookUpdateReceiver(
            session=session,
            settings=settings,
            http_client=client,
        ).receive_update(update)
    return {"ok": True}


class ChatIntegrationDevModePolicy:
    @staticmethod
    def require_dev_mode(settings: Settings) -> None:
        if settings.environment == "production":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
