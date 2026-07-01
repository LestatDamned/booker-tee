from dataclasses import dataclass

from app.features.chat_integrations.actions.upload import ChatUploadCallbackData
from app.features.chat_integrations.handlers.factory import ChatEventHandlers
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


@dataclass(frozen=True)
class ChatUploadCallbackHandler:
    handlers: ChatEventHandlers

    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        account_selection = ChatUploadCallbackData.parse_account_selection(event.callback_data)
        if account_selection is None:
            return None

        return await self.handlers.upload().complete_document_upload(
            event,
            bound_workspace,
            account_selection,
        )
