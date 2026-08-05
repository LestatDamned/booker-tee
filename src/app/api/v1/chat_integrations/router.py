from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError, api_error_responses
from app.api.v1.chat_integrations.schemas import (
    BindTelegramDevLinkApiRequest,
    BindTelegramDevLinkApiResponse,
    TelegramDevLinkConfigApiResponse,
)
from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.chat_integrations.actions.identity import BindChatIdentityCommand
from app.features.chat_integrations.errors import ChatIdentityBindingError
from app.features.chat_integrations.router import ChatIntegrationDevModePolicy
from app.features.chat_integrations.schemas import ChatProviderCode
from app.features.chat_integrations.use_cases.identity import ChatIdentityBinder

router = APIRouter(prefix="/chat-integrations", tags=["chat-integrations"])


def get_chat_identity_binder(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChatIdentityBinder:
    return ChatIdentityBinder(session)


@router.get(
    "/telegram/dev-link",
    response_model=TelegramDevLinkConfigApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
    ),
)
async def read_telegram_dev_link_config(
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
) -> TelegramDevLinkConfigApiResponse:
    del context
    ChatIntegrationDevModePolicy.require_dev_mode(settings)
    return TelegramDevLinkConfigApiResponse()


@router.post(
    "/telegram/dev-link",
    response_model=BindTelegramDevLinkApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def bind_telegram_dev_link(
    request: BindTelegramDevLinkApiRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    binder: Annotated[ChatIdentityBinder, Depends(get_chat_identity_binder)],
) -> BindTelegramDevLinkApiResponse:
    ChatIntegrationDevModePolicy.require_dev_mode(settings)
    try:
        await binder.bind_chat_identity(
            BindChatIdentityCommand(
                workspace_id=context.workspace.workspace.id,
                user_id=context.workspace.user.id,
                provider=ChatProviderCode.TELEGRAM,
                external_user_id=request.external_user_id,
                display_name=request.display_name,
            )
        )
    except ChatIdentityBindingError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="chat_identity_binding_failed",
            message=str(error),
        ) from error
    return BindTelegramDevLinkApiResponse()
