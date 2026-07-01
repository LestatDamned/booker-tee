from sqlalchemy.ext.asyncio import AsyncSession

from app.features.chat_integrations.actions.summary import ChatSummaryPeriodSelection
from app.features.chat_integrations.presentation.dashboard import TelegramDashboardPresenter
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.dashboard import (
    ChatAccountBalanceReader,
    ChatMonthlySummaryReader,
)
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


class ChatDashboardEventHandler:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def show_monthly_summary(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        summary = await ChatMonthlySummaryReader(self.session).read_current_month_summary(
            bound_workspace.context
        )
        return TelegramDashboardPresenter.show_monthly_summary(
            event.conversation,
            bound_workspace.context,
            summary,
        )

    async def show_monthly_summary_for_period(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatSummaryPeriodSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        summary = await ChatMonthlySummaryReader(self.session).read_month_summary(
            context=bound_workspace.context,
            month_start=selection.month_start,
        )
        return TelegramDashboardPresenter.show_monthly_summary(
            event.conversation,
            bound_workspace.context,
            summary,
        )

    async def show_category_summary_for_period(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatSummaryPeriodSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        summary = await ChatMonthlySummaryReader(self.session).read_category_summary(
            context=bound_workspace.context,
            month_start=selection.month_start,
        )
        return TelegramDashboardPresenter.show_category_summary(
            event.conversation,
            bound_workspace.context,
            summary,
        )

    async def show_account_balances(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        balances = await ChatAccountBalanceReader(self.session).read_account_balances(
            bound_workspace.context
        )
        return TelegramDashboardPresenter.show_account_balances(
            event.conversation,
            bound_workspace.context,
            balances,
        )
