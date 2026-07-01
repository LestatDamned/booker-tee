from datetime import date
from decimal import Decimal

from app.features.chat_integrations.actions.summary import ChatSummaryCallbackData
from app.features.chat_integrations.presentation.formatting import (
    TelegramDatePresenter,
    TelegramMoneyPresenter,
)
from app.features.chat_integrations.presentation.workspace import (
    CHAT_WORKSPACE_BUTTON_TEXT,
    TelegramWorkspacePresenter,
)
from app.features.chat_integrations.schemas import (
    ChatConversation,
    OutboundChatButton,
    OutboundChatDeliveryMode,
    OutboundChatMessage,
)
from app.features.chat_integrations.use_cases.dashboard import (
    ChatAccountBalances,
    ChatCategorySummary,
    ChatCategorySummaryRow,
    ChatMonthlySummary,
    ChatPrivateStatus,
)
from app.features.workspaces.service import WorkspaceContext

CHAT_ACCOUNT_BALANCE_ROW_LIMIT = 10


class TelegramAccountBalancePresenter:
    @staticmethod
    def format_balances(balances: ChatAccountBalances) -> str:
        sections: list[str] = []
        if balances.totals:
            total_lines = [
                f"• {TelegramMoneyPresenter.format_money(total.balance, total.currency)}"
                for total in balances.totals
            ]
            sections.append("Итого:\n" + "\n".join(total_lines))

        visible_rows = balances.rows[:CHAT_ACCOUNT_BALANCE_ROW_LIMIT]
        account_lines = [
            (
                f"• {row.account_name}: "
                f"{TelegramMoneyPresenter.format_money(row.balance, row.currency)}"
            )
            for row in visible_rows
        ]
        hidden_count = len(balances.rows) - len(visible_rows)
        if hidden_count > 0:
            account_lines.append(f"…еще счетов: {hidden_count}")
        sections.append("Счета:\n" + "\n".join(account_lines))
        return "\n\n".join(sections)


class TelegramCategorySummaryPresenter:
    @staticmethod
    def format_categories(summary: ChatCategorySummary) -> str:
        if not summary.rows:
            return "За этот период пока нет подтвержденных операций по категориям."

        lines = [
            (
                f"• {row.category_name}: "
                f"{TelegramCategorySummaryPresenter.format_row(row, summary.currency)}"
            )
            for row in summary.rows
        ]
        return "\n".join(lines)

    @staticmethod
    def format_row(row: ChatCategorySummaryRow, currency: str) -> str:
        if row.income > Decimal("0.00") and row.expense > Decimal("0.00"):
            income = TelegramMoneyPresenter.format_money(row.income, currency)
            expense = TelegramMoneyPresenter.format_money(row.expense, currency)
            profit = TelegramMoneyPresenter.format_money(row.profit, currency)
            return f"+{income} / -{expense} / = {profit}"
        if row.income > Decimal("0.00"):
            return f"+{TelegramMoneyPresenter.format_money(row.income, currency)}"
        if row.expense > Decimal("0.00"):
            return f"-{TelegramMoneyPresenter.format_money(row.expense, currency)}"
        return TelegramMoneyPresenter.format_money(row.profit, currency)


class TelegramSummaryPeriodPresenter:
    @staticmethod
    def previous_month(month_start: date) -> date:
        if month_start.month == 1:
            return month_start.replace(year=month_start.year - 1, month=12)
        return month_start.replace(month=month_start.month - 1)

    @staticmethod
    def next_month(month_start: date) -> date:
        if month_start.month == 12:
            return month_start.replace(year=month_start.year + 1, month=1)
        return month_start.replace(month=month_start.month + 1)


class TelegramDashboardPresenter:
    @staticmethod
    def show_monthly_summary(
        conversation: ChatConversation,
        context: WorkspaceContext,
        summary: ChatMonthlySummary,
    ) -> OutboundChatMessage:
        period = (
            f"{TelegramDatePresenter.format_date(summary.date_from)}"
            f"–{TelegramDatePresenter.format_date(summary.date_to)}"
        )
        income = TelegramMoneyPresenter.format_money(summary.income, summary.currency)
        expense = TelegramMoneyPresenter.format_money(summary.expense, summary.currency)
        profit = TelegramMoneyPresenter.format_money(summary.profit, summary.currency)
        previous_month = TelegramSummaryPeriodPresenter.previous_month(summary.date_from)
        next_month = TelegramSummaryPeriodPresenter.next_month(summary.date_from)
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "📊 Сводка\n\n"
                f"{TelegramWorkspacePresenter.format_label(context.workspace.name)}\n"
                f"🗓 {period}\n\n"
                f"🟢 Доход: {income}\n"
                f"🔴 Расход: {expense}\n"
                f"⚖️ Итог: {profit}\n\n"
                f"🔎 К проверке: {summary.total_needing_attention}"
            ),
            buttons=(
                (
                    OutboundChatButton(
                        text="⬅️",
                        callback_data=ChatSummaryCallbackData.build_period_selection(
                            month_start=previous_month,
                        ),
                    ),
                    OutboundChatButton(
                        text=TelegramDatePresenter.format_month(summary.date_from),
                        callback_data=ChatSummaryCallbackData.build_period_selection(
                            month_start=summary.date_from,
                        ),
                    ),
                    OutboundChatButton(
                        text="➡️",
                        callback_data=ChatSummaryCallbackData.build_period_selection(
                            month_start=next_month,
                        ),
                    ),
                ),
                (
                    OutboundChatButton(
                        text="🏷 Категории",
                        callback_data=ChatSummaryCallbackData.build_category_selection(
                            month_start=summary.date_from,
                        ),
                    ),
                ),
                (
                    OutboundChatButton(text="🔎 Проверка", callback_data="review:choose"),
                    OutboundChatButton(text="💳 Балансы", callback_data="balances:show"),
                ),
                (
                    OutboundChatButton(
                        text=CHAT_WORKSPACE_BUTTON_TEXT,
                        callback_data="workspace:choose",
                    ),
                ),
                (OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),
            ),
            delivery_mode=OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE,
        )

    @staticmethod
    def show_category_summary(
        conversation: ChatConversation,
        context: WorkspaceContext,
        summary: ChatCategorySummary,
    ) -> OutboundChatMessage:
        period = (
            f"{TelegramDatePresenter.format_date(summary.date_from)}"
            f"–{TelegramDatePresenter.format_date(summary.date_to)}"
        )
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "🏷 Категории\n\n"
                f"{TelegramWorkspacePresenter.format_label(context.workspace.name)}\n"
                f"🗓 {period}\n\n"
                f"{TelegramCategorySummaryPresenter.format_categories(summary)}"
            ),
            buttons=(
                (
                    OutboundChatButton(
                        text="📊 Сводка",
                        callback_data=ChatSummaryCallbackData.build_period_selection(
                            month_start=summary.date_from,
                        ),
                    ),
                    OutboundChatButton(text="💳 Балансы", callback_data="balances:show"),
                ),
                (OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),
            ),
            delivery_mode=OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE,
        )

    @staticmethod
    def show_account_balances(
        conversation: ChatConversation,
        context: WorkspaceContext,
        balances: ChatAccountBalances,
    ) -> OutboundChatMessage:
        if not balances.rows:
            body = "Пока нет активных счетов."
        else:
            body = TelegramAccountBalancePresenter.format_balances(balances)
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "💳 Балансы\n\n"
                f"{TelegramWorkspacePresenter.format_label(context.workspace.name)}\n\n"
                f"{body}"
            ),
            buttons=(
                (
                    OutboundChatButton(text="📊 Сводка", callback_data="summary:show"),
                    OutboundChatButton(text="🔄 Обновить", callback_data="balances:show"),
                ),
                (
                    OutboundChatButton(
                        text=CHAT_WORKSPACE_BUTTON_TEXT,
                        callback_data="workspace:choose",
                    ),
                ),
                (OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),
            ),
            delivery_mode=OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE,
        )

    @staticmethod
    def show_private_status(
        conversation: ChatConversation,
        context: WorkspaceContext,
        status: ChatPrivateStatus,
        review_url: str | None = None,
    ) -> OutboundChatMessage:
        button_rows: list[tuple[OutboundChatButton, ...]] = []
        if review_url is not None:
            button_rows.append((OutboundChatButton(text="🌐 Web", url=review_url),))
        button_rows.extend(
            (
                (
                    OutboundChatButton(text="🔎 Проверка", callback_data="review:choose"),
                    OutboundChatButton(text="🔄 Обновить", callback_data="status:show"),
                ),
                (
                    OutboundChatButton(
                        text=CHAT_WORKSPACE_BUTTON_TEXT,
                        callback_data="workspace:choose",
                    ),
                ),
                (OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),
            )
        )

        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "📊 Статус\n\n"
                f"{TelegramWorkspacePresenter.format_label(context.workspace.name)}\n"
                f"📄 Документы: {status.documents_needing_attention}\n"
                f"🔎 Проверка: {status.raw_transactions_needing_attention}"
            ),
            buttons=tuple(button_rows),
        )
