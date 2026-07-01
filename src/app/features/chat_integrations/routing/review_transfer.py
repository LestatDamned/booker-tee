from dataclasses import dataclass

from app.features.chat_integrations.actions.review import (
    ChatReviewTransferCallbackData,
    ChatReviewTransferConfirmationCallbackData,
    ChatReviewTransferPairCallbackData,
)
from app.features.chat_integrations.handlers.factory import ChatEventHandlers
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


@dataclass(frozen=True)
class ChatReviewTransferCallbackHandler:
    handlers: ChatEventHandlers

    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        confirmation = ChatReviewTransferConfirmationCallbackData.parse_confirmation_selection(
            event.callback_data
        )
        if confirmation is not None:
            return await self.handlers.review_transfer().confirm_transfer(
                event,
                bound_workspace,
                confirmation,
            )

        pair_selection = ChatReviewTransferPairCallbackData.parse_pair_selection(
            event.callback_data
        )
        if pair_selection is not None:
            return await self.handlers.review_transfer().complete_transfer_pair(
                event,
                bound_workspace,
                pair_selection,
            )

        account_selection = ChatReviewTransferCallbackData.parse_account_selection(
            event.callback_data
        )
        if account_selection is None:
            return None

        return await self.handlers.review_transfer().complete_transfer(
            event,
            bound_workspace,
            account_selection,
        )
