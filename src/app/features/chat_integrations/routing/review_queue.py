from dataclasses import dataclass

from app.features.chat_integrations.actions.review import (
    ChatReviewNavigationCallbackData,
    ChatReviewReturnCallbackData,
)
from app.features.chat_integrations.handlers.factory import ChatEventHandlers
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


@dataclass(frozen=True)
class ChatReviewQueueCallbackHandler:
    handlers: ChatEventHandlers

    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        navigation = ChatReviewNavigationCallbackData.parse_navigation_selection(
            event.callback_data
        )
        if navigation is not None:
            return await self.handlers.review_queue().navigate_item(
                event,
                bound_workspace,
                navigation,
            )

        return_selection = ChatReviewReturnCallbackData.parse_return_selection(event.callback_data)
        if return_selection is not None:
            return await self.handlers.review_queue().return_to_item(
                event,
                bound_workspace,
                return_selection,
            )

        if event.callback_data != "review:next":
            return None

        return await self.handlers.review_queue().show_next_item(event, bound_workspace)
