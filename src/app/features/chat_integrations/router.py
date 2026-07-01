from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.chat_integrations.actions.identity import BindChatIdentityCommand
from app.features.chat_integrations.errors import ChatIdentityBindingError
from app.features.chat_integrations.schemas import ChatProviderCode
from app.features.chat_integrations.use_cases.identity import ChatIdentityBinder
from app.features.chat_integrations.webhook import (
    TELEGRAM_WEBHOOK_SECRET_HEADER,
    TelegramWebhookSecretPolicy,
    TelegramWebhookUpdateReceiver,
)
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter(prefix="/chat-integrations", tags=["chat-integrations"])
templates = create_templates()


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
    async with httpx.AsyncClient(timeout=settings.telegram_polling_timeout_seconds + 10) as client:
        await TelegramWebhookUpdateReceiver(
            session=session,
            settings=settings,
            http_client=client,
        ).receive_update(update)
    return {"ok": True}


@router.get("/telegram/dev-link", response_class=HTMLResponse)
async def telegram_dev_link_form(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    external_user_id: Annotated[str | None, Query()] = None,
    display_name: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    ChatIntegrationDevModePolicy.require_dev_mode(settings)
    return templates.TemplateResponse(
        request,
        "chat_integrations/telegram_dev_link.html",
        {
            "app_name": settings.app_name,
            "current_user": context.user,
            "workspace": context.workspace,
            "external_user_id": external_user_id or "",
            "display_name": display_name or "",
            "error": None,
            "success": None,
        },
    )


@router.post("/telegram/dev-link", response_class=HTMLResponse)
async def telegram_dev_link_submit(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    external_user_id: Annotated[str, Form()],
    display_name: Annotated[str | None, Form()] = None,
) -> Response:
    ChatIntegrationDevModePolicy.require_dev_mode(settings)
    clean_external_user_id = external_user_id.strip()
    clean_display_name = display_name.strip() if display_name else None

    try:
        await ChatIdentityBinder(session).bind_chat_identity(
            BindChatIdentityCommand(
                workspace_id=context.workspace.id,
                user_id=context.user.id,
                provider=ChatProviderCode.TELEGRAM,
                external_user_id=clean_external_user_id,
                display_name=clean_display_name,
            )
        )
    except ChatIdentityBindingError as exc:
        return templates.TemplateResponse(
            request,
            "chat_integrations/telegram_dev_link.html",
            {
                "app_name": settings.app_name,
                "current_user": context.user,
                "workspace": context.workspace,
                "external_user_id": clean_external_user_id,
                "display_name": clean_display_name or "",
                "error": str(exc),
                "success": None,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return templates.TemplateResponse(
        request,
        "chat_integrations/telegram_dev_link.html",
        {
            "app_name": settings.app_name,
            "current_user": context.user,
            "workspace": context.workspace,
            "external_user_id": clean_external_user_id,
            "display_name": clean_display_name or "",
            "error": None,
            "success": "Telegram аккаунт привязан к текущему workspace.",
        },
    )


class ChatIntegrationDevModePolicy:
    @staticmethod
    def require_dev_mode(settings: Settings) -> None:
        if settings.environment == "production":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
