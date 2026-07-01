from dataclasses import dataclass

from app.features.chat_integrations.actions.review import (
    ChatReviewCategoryCallbackData,
    ChatReviewCategoryPageCallbackData,
    ChatReviewPropertyCallbackData,
)
from app.features.chat_integrations.handlers.factory import ChatEventHandlers
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


@dataclass(frozen=True)
class ChatReviewConfirmationCallbackHandler:
    handlers: ChatEventHandlers

    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        property_selection = ChatReviewPropertyCallbackData.parse_property_selection(
            event.callback_data
        )
        if property_selection is not None:
            return await self.handlers.review_confirmation().complete_property_confirmation(
                event,
                bound_workspace,
                property_selection,
            )

        category_page = ChatReviewCategoryPageCallbackData.parse_page_selection(event.callback_data)
        if category_page is not None:
            return await self.handlers.review_confirmation().change_category_page(
                event,
                bound_workspace,
                category_page,
            )

        category_selection = ChatReviewCategoryCallbackData.parse_category_selection(
            event.callback_data
        )
        if category_selection is None:
            return None

        return await self.handlers.review_confirmation().complete_confirmation(
            event,
            bound_workspace,
            category_selection,
        )
