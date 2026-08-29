from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_user_token, hash_user_token
from app.db.base import utc_now
from app.features.chat_integrations.actions.identity import BindChatIdentityCommand
from app.features.chat_integrations.errors import ChatIdentityBindingError
from app.features.chat_integrations.models import ChatIdentityBinding
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.chat_integrations.schemas import ChatProviderCode, ChatUser
from app.features.users.identity_repository import UserTokenRepository
from app.features.users.models import UserTokenPurpose
from app.features.workspaces.repository import WorkspaceRepository
from app.features.workspaces.service import WorkspaceContext

TELEGRAM_LINK_TOKEN_LIFETIME = timedelta(minutes=10)


@dataclass(frozen=True)
class TelegramLinkCode:
    code: str
    expires_at: datetime


class TelegramLinkCodeIssuer:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tokens = UserTokenRepository(session)

    async def issue(self, context: WorkspaceContext) -> TelegramLinkCode:
        code = f"{context.workspace.id}.{generate_user_token()}"
        expires_at = utc_now() + TELEGRAM_LINK_TOKEN_LIFETIME
        await self.tokens.replace_active(
            user_id=context.user.id,
            purpose=UserTokenPurpose.LINK_TELEGRAM,
            token_hash=hash_user_token(code),
            expires_at=expires_at,
        )
        await self.session.commit()
        return TelegramLinkCode(code=code, expires_at=expires_at)


class TelegramLinkCodeBinder:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tokens = UserTokenRepository(session)

    async def bind(self, *, code: str, actor: ChatUser) -> ChatIdentityBinding:
        if actor.provider != ChatProviderCode.TELEGRAM:
            raise ChatIdentityBindingError("Код предназначен только для Telegram.")
        workspace_id = self._read_workspace_id(code)
        token = await self.tokens.consume(
            purpose=UserTokenPurpose.LINK_TELEGRAM,
            token_hash=hash_user_token(code),
        )
        if token is None:
            raise ChatIdentityBindingError("Код недействителен или срок его действия истёк.")
        try:
            return await ChatIdentityBinder(self.session).bind_chat_identity(
                BindChatIdentityCommand(
                    workspace_id=workspace_id,
                    user_id=token.user_id,
                    provider=actor.provider,
                    external_user_id=actor.external_user_id,
                    display_name=actor.display_name,
                )
            )
        except ChatIdentityBindingError:
            await self.session.rollback()
            raise

    @staticmethod
    def _read_workspace_id(code: str) -> UUID:
        try:
            workspace_id, secret = code.strip().split(".", 1)
            if not secret:
                raise ValueError
            return UUID(workspace_id)
        except (ValueError, AttributeError) as error:
            raise ChatIdentityBindingError(
                "Код недействителен или срок его действия истёк."
            ) from error


class ChatIdentityBinder:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chat_integrations = ChatIntegrationRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def bind_chat_identity(self, command: BindChatIdentityCommand) -> ChatIdentityBinding:
        workspace = await self.workspaces.lock_for_update(command.workspace_id)
        if workspace is None or not workspace.is_active:
            raise ChatIdentityBindingError("User is not an active member of this workspace.")
        membership = await self.workspaces.get_active_membership(
            user_id=command.user_id,
            workspace_id=command.workspace_id,
        )
        if membership is None:
            raise ChatIdentityBindingError("User is not an active member of this workspace.")

        existing_binding = await self.chat_integrations.get_active_identity_binding(
            workspace_id=command.workspace_id,
            provider=command.provider,
            external_user_id=command.external_user_id,
        )
        if existing_binding is not None:
            if existing_binding.user_id != command.user_id:
                raise ChatIdentityBindingError("This chat identity is already linked.")
            existing_binding.display_name = command.display_name
            await self.session.commit()
            return existing_binding

        binding = await self.chat_integrations.create_identity_binding(
            workspace_id=command.workspace_id,
            user_id=command.user_id,
            provider=command.provider,
            external_user_id=command.external_user_id,
            display_name=command.display_name,
        )
        await self.session.commit()
        return binding
