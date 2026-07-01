from dataclasses import dataclass
from datetime import timedelta
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.chat_integrations.actions.workspace import ChatWorkspaceSelection
from app.features.chat_integrations.errors import (
    ChatWorkspaceResolutionError,
    ChatWorkspaceSwitchError,
)
from app.features.chat_integrations.models import ChatConversationFlow, ChatIdentityBinding
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.chat_integrations.schemas import InboundChatEvent
from app.features.chat_integrations.use_cases.action_tokens import ChatActionTokenBuilder
from app.features.users.repository import UserRepository
from app.features.workspaces.repository import WorkspaceRepository
from app.features.workspaces.service import WorkspaceContext

CHAT_WORKSPACE_SWITCH_TTL = timedelta(minutes=10)


@dataclass(frozen=True)
class BoundChatWorkspace:
    identity_binding: ChatIdentityBinding
    context: WorkspaceContext


@dataclass(frozen=True)
class ChatWorkspaceChoice:
    id: UUID
    name: str
    is_current: bool


@dataclass(frozen=True)
class StartedChatWorkspaceSelection:
    action_token: str
    workspace_choices: tuple[ChatWorkspaceChoice, ...]


@dataclass(frozen=True)
class SelectedChatWorkspace:
    bound_workspace: BoundChatWorkspace


class WorkspaceChatResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chat_integrations = ChatIntegrationRepository(session)
        self.users = UserRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def require_bound_workspace(self, event: InboundChatEvent) -> BoundChatWorkspace:
        if event.actor is None:
            raise ChatWorkspaceResolutionError("Chat event does not include an actor.")

        bindings = await self.chat_integrations.list_active_identity_bindings_for_external_user(
            provider=event.actor.provider,
            external_user_id=event.actor.external_user_id,
        )
        if not bindings:
            raise ChatWorkspaceResolutionError("Chat identity is not linked to Booker Tee.")
        if len(bindings) > 1:
            raise ChatWorkspaceResolutionError("Chat identity is linked to multiple workspaces.")

        binding = bindings[0]
        user = await self.users.get_active(binding.user_id)
        if user is None:
            raise ChatWorkspaceResolutionError("Linked Booker Tee user is not active.")

        membership = await self.workspaces.get_active_membership(
            user_id=binding.user_id,
            workspace_id=binding.workspace_id,
        )
        if membership is None:
            raise ChatWorkspaceResolutionError("Linked workspace membership is not active.")

        return BoundChatWorkspace(
            identity_binding=binding,
            context=WorkspaceContext(
                user=user,
                workspace=membership.workspace,
                membership=membership,
            ),
        )


class ChatWorkspaceSwitcher:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.chat_integrations = ChatIntegrationRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def start_workspace_selection(
        self,
        bound_workspace: BoundChatWorkspace,
    ) -> StartedChatWorkspaceSelection:
        workspaces = await self.workspaces.list_active_for_user(bound_workspace.context.user.id)
        if not workspaces:
            raise ChatWorkspaceSwitchError("Нет доступных рабочих пространств.")

        choices = tuple(
            ChatWorkspaceChoice(
                id=workspace.id,
                name=workspace.name,
                is_current=workspace.id == bound_workspace.context.workspace.id,
            )
            for workspace in workspaces
        )
        action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=bound_workspace.context.workspace.id,
            user_id=bound_workspace.context.user.id,
            flow=ChatConversationFlow.MAIN_MENU,
            step="choose_workspace",
            action_token=action_token,
            state_payload={
                "workspace_ids": [str(choice.id) for choice in choices],
                "workspace_names": [choice.name for choice in choices],
            },
            expires_at=utc_now() + CHAT_WORKSPACE_SWITCH_TTL,
        )
        await self.session.commit()
        return StartedChatWorkspaceSelection(
            action_token=action_token,
            workspace_choices=choices,
        )

    async def select_workspace(
        self,
        *,
        bound_workspace: BoundChatWorkspace,
        selection: ChatWorkspaceSelection,
    ) -> SelectedChatWorkspace:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=bound_workspace.context.workspace.id,
            user_id=bound_workspace.context.user.id,
            flow=ChatConversationFlow.MAIN_MENU,
            action_token=selection.action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatWorkspaceSwitchError(
                "Выбор рабочего пространства устарел. Открой меню снова."
            )
        if state.step != "choose_workspace":
            raise ChatWorkspaceSwitchError("Сохраненный шаг выбора workspace некорректен.")

        workspace_id = ChatWorkspaceSwitchStateReader.read_workspace_id(
            state.state_payload,
            selection.workspace_index,
        )
        membership = await self.workspaces.get_active_membership(
            user_id=bound_workspace.context.user.id,
            workspace_id=workspace_id,
        )
        if membership is None:
            raise ChatWorkspaceSwitchError("Это рабочее пространство больше недоступно.")

        target_binding = await self._get_or_create_target_binding(
            bound_workspace=bound_workspace,
            workspace_id=workspace_id,
        )
        target_binding.is_active = True
        target_binding.display_name = bound_workspace.identity_binding.display_name
        await self.chat_integrations.deactivate_other_identity_bindings(
            keep_binding_id=target_binding.id,
            provider=bound_workspace.identity_binding.provider,
            external_user_id=bound_workspace.identity_binding.external_user_id,
        )
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return SelectedChatWorkspace(
            bound_workspace=BoundChatWorkspace(
                identity_binding=target_binding,
                context=WorkspaceContext(
                    user=bound_workspace.context.user,
                    workspace=membership.workspace,
                    membership=membership,
                ),
            )
        )

    async def _get_or_create_target_binding(
        self,
        *,
        bound_workspace: BoundChatWorkspace,
        workspace_id: UUID,
    ) -> ChatIdentityBinding:
        target_binding = await self.chat_integrations.get_identity_binding(
            workspace_id=workspace_id,
            provider=bound_workspace.identity_binding.provider,
            external_user_id=bound_workspace.identity_binding.external_user_id,
        )
        if target_binding is not None:
            if target_binding.user_id != bound_workspace.context.user.id:
                raise ChatWorkspaceSwitchError("Этот чат уже привязан к другому пользователю.")
            return target_binding

        return await self.chat_integrations.create_identity_binding(
            workspace_id=workspace_id,
            user_id=bound_workspace.context.user.id,
            provider=bound_workspace.identity_binding.provider,
            external_user_id=bound_workspace.identity_binding.external_user_id,
            display_name=bound_workspace.identity_binding.display_name,
        )


class ChatWorkspaceSwitchStateReader:
    @staticmethod
    def read_workspace_id(payload: dict[str, object], workspace_index: int) -> UUID:
        if workspace_index < 0:
            raise ChatWorkspaceSwitchError("Выбранное рабочее пространство не найдено.")
        workspace_ids = ChatWorkspaceSwitchStateReader._read_list(payload, "workspace_ids")
        try:
            value = workspace_ids[workspace_index]
        except IndexError as exc:
            raise ChatWorkspaceSwitchError("Выбранное рабочее пространство не найдено.") from exc
        if not isinstance(value, str):
            raise ChatWorkspaceSwitchError("Сохраненный выбор workspace некорректен.")
        return UUID(value)

    @staticmethod
    def _read_list(payload: dict[str, object], key: str) -> list[object]:
        value = payload.get(key)
        if not isinstance(value, list):
            raise ChatWorkspaceSwitchError("Сохраненный выбор workspace некорректен.")
        return cast(list[object], value)
