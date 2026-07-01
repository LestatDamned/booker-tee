from sqlalchemy.ext.asyncio import AsyncSession

from app.features.chat_integrations.actions.identity import BindChatIdentityCommand
from app.features.chat_integrations.errors import ChatIdentityBindingError
from app.features.chat_integrations.models import ChatIdentityBinding
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.workspaces.repository import WorkspaceRepository


class ChatIdentityBinder:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chat_integrations = ChatIntegrationRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def bind_chat_identity(self, command: BindChatIdentityCommand) -> ChatIdentityBinding:
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
