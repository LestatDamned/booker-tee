from dataclasses import dataclass

from app.features.chat_integrations.actions.manual import (
    ChatManualAccountCallbackData,
    ChatManualCategoryCallbackData,
    ChatManualCategoryPageCallbackData,
    ChatManualConfirmationCallbackData,
    ChatManualCorrectionCallbackData,
    ChatManualDateCallbackData,
    ChatManualDescriptionCallbackData,
)
from app.features.chat_integrations.handlers.factory import ChatEventHandlers
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


@dataclass(frozen=True)
class ChatManualCallbackHandler:
    handlers: ChatEventHandlers

    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        confirmation = ChatManualConfirmationCallbackData.parse_confirm_action(event.callback_data)
        if confirmation is not None:
            return await self.handlers.manual().confirm_operation(
                event,
                bound_workspace,
                confirmation,
            )

        correction_selection = ChatManualCorrectionCallbackData.parse_correction_selection(
            event.callback_data
        )
        if correction_selection is not None:
            return await self.handlers.manual().select_correction(
                event,
                bound_workspace,
                correction_selection,
            )

        account_selection = ChatManualAccountCallbackData.parse_account_selection(
            event.callback_data
        )
        if account_selection is not None:
            return await self.handlers.manual().select_account(
                event,
                bound_workspace,
                account_selection,
            )

        category_selection = ChatManualCategoryCallbackData.parse_category_selection(
            event.callback_data
        )
        if category_selection is not None:
            return await self.handlers.manual().select_category(
                event,
                bound_workspace,
                category_selection,
            )

        category_page_selection = ChatManualCategoryPageCallbackData.parse_page_selection(
            event.callback_data
        )
        if category_page_selection is not None:
            return await self.handlers.manual().change_category_page(
                event,
                bound_workspace,
                category_page_selection,
            )

        date_selection = ChatManualDateCallbackData.parse_date_selection(event.callback_data)
        if date_selection is not None:
            return await self.handlers.manual().select_date(
                event,
                bound_workspace,
                date_selection,
            )

        description_selection = ChatManualDescriptionCallbackData.parse_description_selection(
            event.callback_data
        )
        if description_selection is None:
            return None

        return await self.handlers.manual().skip_description(
            event,
            bound_workspace,
            description_selection,
        )
