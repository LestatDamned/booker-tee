from dataclasses import dataclass

from app.features.chat_integrations.actions.review import (
    ChatReviewActionConfirmationCallbackData,
    ChatReviewCallbackData,
)
from app.features.chat_integrations.handlers.factory import ChatEventHandlers
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


@dataclass(frozen=True)
class ChatReviewActionCallbackHandler:
    handlers: ChatEventHandlers

    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        action_confirmation = ChatReviewActionConfirmationCallbackData.parse_confirmation_selection(
            event.callback_data
        )
        if action_confirmation is not None:
            return await self.handlers.review_action().confirm_action(
                event,
                bound_workspace,
                action_confirmation,
            )

        review_action = ChatReviewCallbackData.parse_action(event.callback_data)
        if review_action is None:
            return None

        return await self.handlers.review_action().apply_action(
            event,
            bound_workspace,
            review_action,
        )
