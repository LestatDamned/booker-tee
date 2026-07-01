from dataclasses import dataclass

from app.features.chat_integrations.actions.workspace import ChatWorkspaceCallbackData
from app.features.chat_integrations.handlers.factory import ChatEventHandlers
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


@dataclass(frozen=True)
class ChatWorkspaceCallbackHandler:
    handlers: ChatEventHandlers

    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        workspace_selection = ChatWorkspaceCallbackData.parse_workspace_selection(
            event.callback_data
        )
        if workspace_selection is not None:
            return await self.handlers.workspace().select_workspace(
                event,
                bound_workspace,
                workspace_selection,
            )

        if event.callback_data != "workspace:choose":
            return None

        return await self.handlers.workspace().start_workspace_selection(event, bound_workspace)
