from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.actions.workspace import ChatWorkspaceSelection
from app.features.chat_integrations.application import ChatReviewUrlBuilder
from app.features.chat_integrations.errors import ChatWorkspaceSwitchError
from app.features.chat_integrations.presentation.workspace import TelegramWorkspacePresenter
from app.features.chat_integrations.presenters import TelegramMainMenuPresenter
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.dashboard import ChatPrivateStatusReader
from app.features.chat_integrations.use_cases.workspace import (
    BoundChatWorkspace,
    ChatWorkspaceSwitcher,
)


class ChatWorkspaceEventHandler:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None,
    ) -> None:
        self.session = session
        self.settings = settings

    async def start_workspace_selection(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        try:
            selection = await ChatWorkspaceSwitcher(self.session).start_workspace_selection(
                bound_workspace
            )
        except ChatWorkspaceSwitchError as exc:
            return TelegramWorkspacePresenter.show_switch_error(
                event.conversation,
                str(exc),
            )

        return TelegramWorkspacePresenter.show_menu(event.conversation, selection)

    async def select_workspace(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        workspace_selection: ChatWorkspaceSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        try:
            selected = await ChatWorkspaceSwitcher(self.session).select_workspace(
                bound_workspace=bound_workspace,
                selection=workspace_selection,
            )
        except ChatWorkspaceSwitchError as exc:
            return TelegramWorkspacePresenter.show_switch_error(
                event.conversation,
                str(exc),
            )

        status = await ChatPrivateStatusReader(self.session).read_status(
            selected.bound_workspace.context
        )
        return TelegramMainMenuPresenter.show_bound_menu(
            event.conversation,
            selected.bound_workspace.context,
            status,
            ChatReviewUrlBuilder.build_imports_url(self.settings),
            callback_notification="Готово: пространство переключено",
        )
