from dataclasses import dataclass

from app.features.chat_integrations.actions.summary import ChatSummaryCallbackData
from app.features.chat_integrations.handlers.factory import ChatEventHandlers
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


@dataclass(frozen=True)
class ChatDashboardCallbackHandler:
    handlers: ChatEventHandlers

    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        period_selection = ChatSummaryCallbackData.parse_period_selection(event.callback_data)
        if period_selection is not None:
            return await self.handlers.dashboard().show_monthly_summary_for_period(
                event,
                bound_workspace,
                period_selection,
            )

        category_selection = ChatSummaryCallbackData.parse_category_selection(event.callback_data)
        if category_selection is not None:
            return await self.handlers.dashboard().show_category_summary_for_period(
                event,
                bound_workspace,
                category_selection,
            )

        if event.callback_data == "summary:show":
            return await self.handlers.dashboard().show_monthly_summary(event, bound_workspace)

        if event.callback_data == "balances:show":
            return await self.handlers.dashboard().show_account_balances(event, bound_workspace)

        return None
