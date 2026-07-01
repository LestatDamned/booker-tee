from datetime import date
from decimal import Decimal

from app.features.chat_integrations.application import (
    ChatAccountBalances,
    ChatCategorySummary,
    ChatCategorySummaryRow,
    ChatManualOperationConfirmation,
    ChatManualOperationResult,
    ChatMonthlySummary,
    ChatPrivateStatus,
    ChatReviewNavigationBoundary,
    ChatReviewQueueItem,
    ChatReviewTransferPairChoice,
    StartedChatDocumentUpload,
    StartedChatManualAccountSelection,
    StartedChatManualAmountInput,
    StartedChatManualCategorySelection,
    StartedChatManualCorrectionSelection,
    StartedChatManualDateInput,
    StartedChatManualDateSelection,
    StartedChatManualDescriptionInput,
    StartedChatReviewActionConfirmation,
    StartedChatReviewCategorySelection,
    StartedChatReviewPropertySelection,
    StartedChatReviewRulePatternInput,
    StartedChatReviewRulePatternSelection,
    StartedChatReviewRuleSuggestion,
    StartedChatReviewTransferConfirmation,
    StartedChatReviewTransferSelection,
    StartedChatWorkspaceSelection,
)
from app.features.chat_integrations.commands import (
    ChatManualAccountCallbackData,
    ChatManualCategoryCallbackData,
    ChatManualConfirmationCallbackData,
    ChatManualCorrectionCallbackData,
    ChatManualDateCallbackData,
    ChatManualDescriptionCallbackData,
    ChatReviewActionConfirmationCallbackData,
    ChatReviewCallbackData,
    ChatReviewCategoryCallbackData,
    ChatReviewCategoryPageCallbackData,
    ChatReviewNavigationCallbackData,
    ChatReviewPropertyCallbackData,
    ChatReviewReturnCallbackData,
    ChatReviewRulePatternCallbackData,
    ChatReviewRuleSuggestionCallbackData,
    ChatReviewTransferCallbackData,
    ChatReviewTransferConfirmationCallbackData,
    ChatReviewTransferPairCallbackData,
    ChatSummaryCallbackData,
    ChatUploadCallbackData,
    ChatWorkspaceCallbackData,
)
from app.features.chat_integrations.schemas import (
    ChatConversation,
    ChatUser,
    OutboundChatButton,
    OutboundChatDeliveryMode,
    OutboundChatMessage,
)
from app.features.imports.models import UploadedDocument, UploadedDocumentStatus
from app.features.ledger.models import OperationType
from app.features.workspaces.service import WorkspaceContext

CHAT_ACCOUNT_BALANCE_ROW_LIMIT = 10
CHAT_CATEGORY_SUMMARY_ROW_LIMIT = 10
CHAT_MAIN_MENU_BUTTON_TEXT = "🏠 Меню"
CHAT_WORKSPACE_BUTTON_TEXT = "🗂️ Пространство"
CHAT_WORKSPACE_TITLE = "🗂️ Рабочее пространство"
CHAT_WORKSPACE_CHOICE_PREFIX = "🗂️ "


class TelegramWorkspacePresenter:
    @staticmethod
    def format_label(workspace_name: str) -> str:
        return f"{CHAT_WORKSPACE_CHOICE_PREFIX}{workspace_name}"


class TelegramDatePresenter:
    MONTH_NAMES = {
        1: "Январь",
        2: "Февраль",
        3: "Март",
        4: "Апрель",
        5: "Май",
        6: "Июнь",
        7: "Июль",
        8: "Август",
        9: "Сентябрь",
        10: "Октябрь",
        11: "Ноябрь",
        12: "Декабрь",
    }

    @staticmethod
    def format_date(value: date) -> str:
        return value.strftime("%d.%m.%Y")

    @classmethod
    def format_month(cls, value: date) -> str:
        return f"{cls.MONTH_NAMES[value.month]} {value.year}"


class TelegramMoneyPresenter:
    @staticmethod
    def format_money(amount: Decimal, currency: str) -> str:
        return f"{amount:.2f} {currency}".strip()


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

        rows = summary.rows[:CHAT_CATEGORY_SUMMARY_ROW_LIMIT]
        lines = [
            (
                f"• {row.category_name}: "
                f"{TelegramCategorySummaryPresenter.format_row(row, summary.currency)}"
            )
            for row in rows
        ]
        hidden_count = len(summary.rows) - len(rows)
        if hidden_count > 0:
            lines.append(f"…еще категорий: {hidden_count}")
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


class TelegramMainMenuPresenter:
    @staticmethod
    def _show_review_workspace(
        *,
        conversation: ChatConversation,
        text: str,
        buttons: tuple[tuple[OutboundChatButton, ...], ...],
        callback_notification: str | None = None,
    ) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=text,
            buttons=buttons,
            delivery_mode=OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE,
            callback_notification=callback_notification,
        )

    @staticmethod
    def show_welcome_menu(conversation: ChatConversation) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "👋 Booker Tee\n\n"
                "Подключи аккаунт, чтобы загружать выписки и разбирать операции в чате."
            ),
            buttons=(
                (
                    OutboundChatButton(text="🔗 Подключить", callback_data="link:start"),
                    OutboundChatButton(text="❔ Помощь", callback_data="help:show"),
                ),
            ),
        )

    @staticmethod
    def show_help(conversation: ChatConversation) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "❔ Что умеет бот\n\n"
                "📎 Загружает выписки файлом\n"
                "🔎 Показывает строки на проверку\n"
                "✅ Подтверждает операции кнопками\n"
                "🔁 Помогает не считать переводы как расход"
            ),
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_bound_menu(
        conversation: ChatConversation,
        context: WorkspaceContext,
        status: ChatPrivateStatus,
        review_url: str | None = None,
        callback_notification: str | None = None,
    ) -> OutboundChatMessage:
        user_label = context.user.name or context.user.email
        button_rows: list[tuple[OutboundChatButton, ...]] = [
            (
                OutboundChatButton(text="📊 Сводка", callback_data="summary:show"),
                OutboundChatButton(text="🔎 Проверка", callback_data="review:next"),
            ),
            (
                OutboundChatButton(text="📎 Выписка", callback_data="upload:start"),
                OutboundChatButton(text="➕ Операция", callback_data="manual:start"),
            ),
            (
                OutboundChatButton(text="💳 Балансы", callback_data="balances:show"),
                OutboundChatButton(
                    text=CHAT_WORKSPACE_BUTTON_TEXT,
                    callback_data="workspace:choose",
                ),
            ),
        ]
        if review_url is not None:
            button_rows.append((OutboundChatButton(text="🌐 Web", url=review_url),))
        button_rows.append((OutboundChatButton(text="❔ Помощь", callback_data="help:show"),))

        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "✅ Booker Tee подключен\n\n"
                f"👤 {user_label}\n"
                f"{TelegramWorkspacePresenter.format_label(context.workspace.name)}\n"
                f"⚠️ К проверке: {status.total_needing_attention}\n\n"
                "📎 Выписку можно отправить файлом в этот чат."
            ),
            buttons=tuple(button_rows),
            callback_notification=callback_notification,
        )

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
                    OutboundChatButton(text="🔎 Проверка", callback_data="review:next"),
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
                    OutboundChatButton(text="🔎 Проверка", callback_data="review:next"),
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

    @staticmethod
    def show_workspace_menu(
        conversation: ChatConversation,
        selection: StartedChatWorkspaceSelection,
    ) -> OutboundChatMessage:
        rows: list[tuple[OutboundChatButton, ...]] = []
        for index, choice in enumerate(selection.workspace_choices):
            prefix = "✅ " if choice.is_current else CHAT_WORKSPACE_CHOICE_PREFIX
            rows.append(
                (
                    OutboundChatButton(
                        text=f"{prefix}{choice.name}",
                        callback_data=ChatWorkspaceCallbackData.build_workspace_selection(
                            action_token=selection.action_token,
                            workspace_index=index,
                        ),
                    ),
                )
            )
        rows.append(
            (
                OutboundChatButton(
                    text=CHAT_MAIN_MENU_BUTTON_TEXT,
                    callback_data="main:menu",
                ),
            )
        )
        return OutboundChatMessage(
            conversation=conversation,
            text=f"{CHAT_WORKSPACE_TITLE}\n\nВыбери, с чем сейчас работаем.",
            buttons=tuple(rows),
            delivery_mode=OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE,
        )

    @staticmethod
    def show_workspace_switch_error(
        conversation: ChatConversation,
        message: str,
    ) -> OutboundChatMessage:
        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text=f"⚠️ Не получилось переключить пространство.\n\n{message}",
            buttons=(
                (
                    OutboundChatButton(
                        text=CHAT_WORKSPACE_BUTTON_TEXT,
                        callback_data="workspace:choose",
                    ),
                    OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),
                ),
            ),
            callback_notification="Не получилось",
        )

    @staticmethod
    def show_next_review_item(
        conversation: ChatConversation,
        item: ChatReviewQueueItem,
        action_token: str,
        review_url: str | None = None,
        callback_notification: str | None = None,
    ) -> OutboundChatMessage:
        action_rows: list[tuple[OutboundChatButton, ...]]
        manual_category_button = OutboundChatButton(
            text="🏷 Категория",
            callback_data=ChatReviewCallbackData.build_confirm_action(action_token=action_token),
        )
        transfer_button = OutboundChatButton(
            text="🔁 Перевод",
            callback_data=ChatReviewCallbackData.build_transfer_action(action_token=action_token),
        )
        if item.suggested_category_id is not None:
            action_rows = [
                (
                    OutboundChatButton(
                        text="✅ Принять",
                        callback_data=ChatReviewCallbackData.build_accept_suggestion_action(
                            action_token=action_token,
                        ),
                    ),
                    manual_category_button,
                ),
                (transfer_button,),
            ]
        else:
            action_rows = [(manual_category_button, transfer_button)]
        secondary_action_rows: list[tuple[OutboundChatButton, ...]] = [
            (
                OutboundChatButton(
                    text="🚫 Не учитывать",
                    callback_data=ChatReviewCallbackData.build_ignore_action(
                        action_token=action_token
                    ),
                ),
            ),
        ]
        if item.status == "possible_duplicate":
            secondary_action_rows = [
                (
                    OutboundChatButton(
                        text="🗑 Дубль",
                        callback_data=ChatReviewCallbackData.build_duplicate_action(
                            action_token=action_token
                        ),
                    ),
                    OutboundChatButton(
                        text="✅ Не дубль",
                        callback_data=ChatReviewCallbackData.build_mark_unique_action(
                            action_token=action_token
                        ),
                    ),
                ),
                (
                    OutboundChatButton(
                        text="🚫 Не учитывать",
                        callback_data=ChatReviewCallbackData.build_ignore_action(
                            action_token=action_token
                        ),
                    ),
                ),
            ]
        navigation_rows: list[tuple[OutboundChatButton, ...]] = []
        if review_url is not None:
            navigation_rows.append((OutboundChatButton(text="🌐 Web", url=review_url),))
        navigation_rows.append(
            (
                OutboundChatButton(
                    text="⬅️ Пред.",
                    callback_data=ChatReviewNavigationCallbackData.build_previous_action(
                        action_token=action_token,
                    ),
                ),
                OutboundChatButton(
                    text="➡️ След.",
                    callback_data=ChatReviewNavigationCallbackData.build_next_action(
                        action_token=action_token,
                    ),
                ),
            )
        )
        navigation_rows.append((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),))

        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text=TelegramReviewQueueCardPresenter.format_item(item),
            buttons=(
                *action_rows,
                *secondary_action_rows,
                *navigation_rows,
            ),
            callback_notification=callback_notification,
        )

    @staticmethod
    def show_review_action_confirmation(
        conversation: ChatConversation,
        confirmation: StartedChatReviewActionConfirmation,
    ) -> OutboundChatMessage:
        if confirmation.action == ChatReviewCallbackData.DUPLICATE_ACTION:
            title = "🗑 Пометить как дубль?"
            consequence = "Эта строка не будет учтена повторно."
            confirm_label = "✅ Да, это дубль"
        else:
            title = "🚫 Не учитывать строку?"
            consequence = "Она не попадет в доходы, расходы или переводы."
            confirm_label = "✅ Да, не учитывать"

        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text=(
                f"{title}\n\n"
                f"{consequence}\n\n"
                f"{TelegramReviewQueueCardPresenter.format_item(confirmation.item)}"
            ),
            buttons=(
                (
                    OutboundChatButton(
                        text=confirm_label,
                        callback_data=ChatReviewActionConfirmationCallbackData.build_confirm_action(
                            action_token=confirmation.action_token,
                        ),
                    ),
                ),
                (
                    OutboundChatButton(
                        text="🔎 К строке",
                        callback_data=ChatReviewReturnCallbackData.build_return_action(
                            action_token=confirmation.action_token,
                        ),
                    ),
                ),
            ),
        )

    @staticmethod
    def show_review_navigation_boundary(
        conversation: ChatConversation,
        boundary: ChatReviewNavigationBoundary,
    ) -> OutboundChatMessage:
        text = (
            "Это первая строка в выписке."
            if boundary.direction == "prev"
            else "Это последняя строка в выписке."
        )
        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text=f"🔎 Проверка\n\n{text}",
            buttons=(
                (
                    OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),
                    OutboundChatButton(text="📊 Статус", callback_data="status:show"),
                ),
            ),
        )

    @staticmethod
    def show_review_category_menu(
        conversation: ChatConversation,
        selection: StartedChatReviewCategorySelection,
    ) -> OutboundChatMessage:
        category_buttons = tuple(
            (
                OutboundChatButton(
                    text=category.name,
                    callback_data=ChatReviewCategoryCallbackData.build_category_selection(
                        action_token=selection.action_token,
                        category_index=selection.page_start_index + index,
                    ),
                ),
            )
            for index, category in enumerate(selection.category_choices)
        )
        page_buttons: list[OutboundChatButton] = []
        if selection.page_index > 0:
            page_buttons.append(
                OutboundChatButton(
                    text="⬅️ Пред.",
                    callback_data=ChatReviewCategoryPageCallbackData.build_page_action(
                        action_token=selection.action_token,
                        page_index=selection.page_index - 1,
                    ),
                )
            )
        if selection.page_index + 1 < selection.page_count:
            page_buttons.append(
                OutboundChatButton(
                    text="➡️ Еще",
                    callback_data=ChatReviewCategoryPageCallbackData.build_page_action(
                        action_token=selection.action_token,
                        page_index=selection.page_index + 1,
                    ),
                )
            )
        page_row = (tuple(page_buttons),) if page_buttons else ()
        page_hint = (
            f"\nСтраница {selection.page_index + 1} из {selection.page_count}"
            if selection.page_count > 1
            else ""
        )
        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text=(
                f"Выбери категорию.{page_hint}\n\n"
                f"{TelegramReviewQueueCardPresenter.format_item(selection.item)}"
            ),
            buttons=category_buttons
            + page_row
            + (
                (
                    OutboundChatButton(
                        text="🔎 К строке",
                        callback_data=ChatReviewReturnCallbackData.build_return_action(
                            action_token=selection.action_token,
                        ),
                    ),
                ),
            ),
        )

    @staticmethod
    def show_review_property_menu(
        conversation: ChatConversation,
        selection: StartedChatReviewPropertySelection,
    ) -> OutboundChatMessage:
        property_buttons = tuple(
            (
                OutboundChatButton(
                    text=property_.name,
                    callback_data=ChatReviewPropertyCallbackData.build_property_selection(
                        action_token=selection.action_token,
                        property_index=index,
                    ),
                ),
            )
            for index, property_ in enumerate(selection.property_choices)
        )
        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text=(
                "Выбери объект для операции.\n\n"
                f"Категория: {selection.category_name}\n\n"
                f"{TelegramReviewQueueCardPresenter.format_item(selection.item)}"
            ),
            buttons=property_buttons
            + (
                (
                    OutboundChatButton(
                        text="⬅️ Назад",
                        callback_data=ChatReviewReturnCallbackData.build_return_action(
                            action_token=selection.action_token,
                        ),
                    ),
                ),
            ),
        )

    @staticmethod
    def show_review_transfer_account_menu(
        conversation: ChatConversation,
        selection: StartedChatReviewTransferSelection,
    ) -> OutboundChatMessage:
        pair_buttons = tuple(
            (
                OutboundChatButton(
                    text=TelegramReviewTransferChoicePresenter.pair_button_text(pair),
                    callback_data=ChatReviewTransferPairCallbackData.build_pair_selection(
                        action_token=selection.action_token,
                        pair_index=index,
                    ),
                ),
            )
            for index, pair in enumerate(selection.pair_choices)
        )
        account_buttons = tuple(
            (
                OutboundChatButton(
                    text=f"{account.name} / {account.currency}",
                    callback_data=ChatReviewTransferCallbackData.build_account_selection(
                        action_token=selection.action_token,
                        account_index=index,
                    ),
                ),
            )
            for index, account in enumerate(selection.account_choices)
        )
        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text=(
                "Выбери парную строку или встречный счет для перевода.\n\n"
                f"{TelegramReviewQueueCardPresenter.format_item(selection.item)}"
            ),
            buttons=pair_buttons
            + account_buttons
            + (
                (
                    OutboundChatButton(
                        text="⬅️ Назад",
                        callback_data=ChatReviewReturnCallbackData.build_return_action(
                            action_token=selection.action_token,
                        ),
                    ),
                ),
            ),
        )

    @staticmethod
    def show_review_transfer_confirmation(
        conversation: ChatConversation,
        confirmation: StartedChatReviewTransferConfirmation,
    ) -> OutboundChatMessage:
        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text=(
                "🔁 Подтвердить перевод?\n\n"
                "Перевод не попадет в доходы или расходы.\n\n"
                f"Цель: {confirmation.target_label}\n\n"
                f"{TelegramReviewQueueCardPresenter.format_item(confirmation.item)}"
            ),
            buttons=(
                (
                    OutboundChatButton(
                        text="✅ Да, это перевод",
                        callback_data=ChatReviewTransferConfirmationCallbackData.build_confirm_action(
                            action_token=confirmation.action_token,
                        ),
                    ),
                ),
                (
                    OutboundChatButton(
                        text="⬅️ Выбор",
                        callback_data=ChatReviewCallbackData.build_transfer_action(
                            action_token=confirmation.action_token,
                        ),
                    ),
                ),
            ),
        )

    @staticmethod
    def show_review_rule_suggestion(
        conversation: ChatConversation,
        suggestion: StartedChatReviewRuleSuggestion,
    ) -> OutboundChatMessage:
        choose_pattern_row: tuple[tuple[OutboundChatButton, ...], ...] = ()
        if suggestion.alternative_patterns:
            choose_pattern_row = (
                (
                    OutboundChatButton(
                        text="✏️ Другой признак",
                        callback_data=ChatReviewRuleSuggestionCallbackData.build_choose_pattern_action(
                            action_token=suggestion.action_token,
                        ),
                    ),
                ),
            )
        manual_pattern_row = (
            (
                OutboundChatButton(
                    text="✍️ Ввести вручную",
                    callback_data=ChatReviewRuleSuggestionCallbackData.build_enter_pattern_action(
                        action_token=suggestion.action_token,
                    ),
                ),
            ),
        )
        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text=(
                f"✅ {suggestion.action_label}\n\n"
                "Запомнить для похожих операций?\n\n"
                f"Признак: {suggestion.pattern}\n"
                f"Категория: {suggestion.category_name}\n\n"
                "Если в новых выписках встречу этот признак, предложу эту категорию."
            ),
            buttons=(
                (
                    OutboundChatButton(
                        text="✅ Запомнить",
                        callback_data=ChatReviewRuleSuggestionCallbackData.build_save_action(
                            action_token=suggestion.action_token,
                        ),
                    ),
                    OutboundChatButton(
                        text="Не сейчас",
                        callback_data=ChatReviewRuleSuggestionCallbackData.build_skip_action(
                            action_token=suggestion.action_token,
                        ),
                    ),
                ),
                *choose_pattern_row,
                *manual_pattern_row,
            ),
        )

    @staticmethod
    def show_review_rule_pattern_input(
        conversation: ChatConversation,
        selection: StartedChatReviewRulePatternInput,
    ) -> OutboundChatMessage:
        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text=(
                "✍️ Напиши признак для правила.\n\n"
                f"Категория: {selection.category_name}\n\n"
                "Например: KRASNOE&BELOE"
            ),
            buttons=(
                (
                    OutboundChatButton(
                        text="Не сейчас",
                        callback_data=ChatReviewRuleSuggestionCallbackData.build_skip_action(
                            action_token=selection.action_token,
                        ),
                    ),
                ),
            ),
        )

    @staticmethod
    def show_review_rule_pattern_menu(
        conversation: ChatConversation,
        selection: StartedChatReviewRulePatternSelection,
    ) -> OutboundChatMessage:
        pattern_buttons = tuple(
            (
                OutboundChatButton(
                    text=pattern,
                    callback_data=ChatReviewRulePatternCallbackData.build_pattern_selection(
                        action_token=selection.action_token,
                        pattern_index=index,
                    ),
                ),
            )
            for index, pattern in enumerate(selection.pattern_choices)
        )
        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text=(
                "Выбери признак для правила.\n\n"
                f"Категория: {selection.category_name}\n\n"
                "По этому тексту бот будет искать похожие операции."
            ),
            buttons=pattern_buttons
            + (
                (
                    OutboundChatButton(
                        text="✍️ Ввести вручную",
                        callback_data=ChatReviewRuleSuggestionCallbackData.build_enter_pattern_action(
                            action_token=selection.action_token,
                        ),
                    ),
                ),
                (
                    OutboundChatButton(
                        text="Не сейчас",
                        callback_data=ChatReviewRuleSuggestionCallbackData.build_skip_action(
                            action_token=selection.action_token,
                        ),
                    ),
                ),
            ),
        )

    @staticmethod
    def show_review_queue_empty(
        conversation: ChatConversation,
        callback_notification: str | None = "Готово",
    ) -> OutboundChatMessage:
        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text="✅ Сейчас нечего проверять.",
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
            callback_notification=callback_notification,
        )

    @staticmethod
    def show_review_action_applied(
        conversation: ChatConversation,
        action_label: str,
    ) -> OutboundChatMessage:
        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text=f"✅ Готово: {action_label}.",
            buttons=(
                (
                    OutboundChatButton(text="➡️ След.", callback_data="review:next"),
                    OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),
                ),
            ),
            callback_notification="Готово",
        )

    @staticmethod
    def show_review_action_error(
        conversation: ChatConversation,
        message: str,
    ) -> OutboundChatMessage:
        if TelegramReviewActionErrorPresenter.is_stale_button_error(message):
            return TelegramMainMenuPresenter.show_review_stale_button_error(conversation)

        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text=f"⚠️ Не получилось применить действие.\n\n{message}",
            buttons=(
                (
                    OutboundChatButton(text="➡️ След.", callback_data="review:next"),
                    OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),
                ),
            ),
            callback_notification="Не получилось",
        )

    @staticmethod
    def show_review_stale_button_error(conversation: ChatConversation) -> OutboundChatMessage:
        return TelegramMainMenuPresenter._show_review_workspace(
            conversation=conversation,
            text=(
                "⚠️ Кнопка устарела\n\n"
                "Эта кнопка уже неактуальна. Открой актуальную строку проверки."
            ),
            buttons=(
                (
                    OutboundChatButton(
                        text="🔎 Актуальная строка",
                        callback_data="review:next",
                    ),
                    OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),
                ),
            ),
            callback_notification="Кнопка устарела",
        )

    @staticmethod
    def show_group_private_actions_notice(conversation: ChatConversation) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "В рабочих чатах Booker Tee будет писать только безопасные уведомления.\n\n"
                "Приватный статус, проверка и финансовые действия доступны только "
                "в личном чате с ботом."
            ),
            buttons=((OutboundChatButton(text="❔ Помощь", callback_data="help:show"),),),
        )

    @staticmethod
    def show_upload_not_ready(conversation: ChatConversation) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "⚠️ Загрузка временно недоступна.\n\nПопробуй позже или открой импорт в Booker Tee."
            ),
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_upload_instructions(conversation: ChatConversation) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "📎 Загрузка выписки\n\n"
                "Отправь PDF или XLSX файлом в этот чат.\n"
                "После загрузки я попрошу выбрать счет."
            ),
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_manual_operation_not_ready(conversation: ChatConversation) -> OutboundChatMessage:
        return TelegramMainMenuPresenter.show_manual_operation_type_menu(conversation)

    @staticmethod
    def show_manual_operation_type_menu(conversation: ChatConversation) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=("➕ Ручная операция\n\nВыбери тип. Дальше бот покажет только нужные кнопки."),
            buttons=(
                (
                    OutboundChatButton(text="💸 Расход", callback_data="manual:expense"),
                    OutboundChatButton(text="💰 Доход", callback_data="manual:income"),
                ),
                (OutboundChatButton(text="🔁 Перевод", callback_data="manual:transfer"),),
                (OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),
            ),
        )

    @staticmethod
    def show_manual_account_menu(
        conversation: ChatConversation,
        selection: StartedChatManualAccountSelection,
    ) -> OutboundChatMessage:
        account_buttons = tuple(
            (
                OutboundChatButton(
                    text=f"{choice.name} / {choice.currency}",
                    callback_data=ChatManualAccountCallbackData.build_account_selection(
                        action_token=selection.action_token,
                        account_index=index,
                    ),
                ),
            )
            for index, choice in enumerate(selection.account_choices)
        )
        source_hint = (
            f"\n\nОткуда: {selection.source_account_name}"
            if selection.source_account_name is not None
            else ""
        )
        question = (
            "Куда перевести?"
            if selection.source_account_name is not None
            else TelegramManualOperationPresenter.account_question(selection.operation_type)
        )
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                f"{TelegramManualOperationPresenter.operation_type_label(selection.operation_type)}"
                f"{source_hint}\n\n"
                f"{question}"
            ),
            buttons=account_buttons
            + ((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_manual_amount_prompt(
        conversation: ChatConversation,
        amount_input: StartedChatManualAmountInput,
    ) -> OutboundChatMessage:
        direction = (
            f"{amount_input.account_name} → {amount_input.destination_account_name}"
            if amount_input.destination_account_name is not None
            else amount_input.account_name
        )
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                f"{TelegramManualOperationPresenter.operation_type_label(amount_input.operation_type)}"
                f"\n\nСчет: {direction}\n"
                f"Валюта: {amount_input.currency}\n\n"
                "Напиши сумму одним числом.\n"
                "Например: 1250 или 1 250,50"
            ),
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_manual_amount_error(
        conversation: ChatConversation,
        message: str,
    ) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=f"⚠️ {message}\n\nНапиши только сумму. Например: 1250",
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_manual_date_menu(
        conversation: ChatConversation,
        selection: StartedChatManualDateSelection,
    ) -> OutboundChatMessage:
        direction = TelegramManualOperationPresenter.account_direction(selection)
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                f"{TelegramManualOperationPresenter.operation_type_label(selection.operation_type)}"
                "\n\n"
                f"Сумма: {selection.amount:.2f} {selection.currency}\n"
                f"Счет: {direction}\n\n"
                "Когда была операция?"
            ),
            buttons=(
                (
                    OutboundChatButton(
                        text="📅 Сегодня",
                        callback_data=ChatManualDateCallbackData.build_today_action(
                            action_token=selection.action_token,
                        ),
                    ),
                    OutboundChatButton(
                        text="↩️ Вчера",
                        callback_data=ChatManualDateCallbackData.build_yesterday_action(
                            action_token=selection.action_token,
                        ),
                    ),
                ),
                (
                    OutboundChatButton(
                        text="✍️ Другая",
                        callback_data=ChatManualDateCallbackData.build_custom_action(
                            action_token=selection.action_token,
                        ),
                    ),
                ),
                (OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),
            ),
        )

    @staticmethod
    def show_manual_date_input_prompt(
        conversation: ChatConversation,
        date_input: StartedChatManualDateInput,
    ) -> OutboundChatMessage:
        direction = TelegramManualOperationPresenter.account_direction(date_input)
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                f"{TelegramManualOperationPresenter.operation_type_label(date_input.operation_type)}"
                "\n\n"
                f"Сумма: {date_input.amount:.2f} {date_input.currency}\n"
                f"Счет: {direction}\n\n"
                "Напиши дату.\n"
                "Например: 30.06.2026"
            ),
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_manual_date_error(
        conversation: ChatConversation,
        message: str,
    ) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=f"⚠️ {message}\n\nНапиши дату. Например: 30.06.2026",
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_manual_category_menu(
        conversation: ChatConversation,
        selection: StartedChatManualCategorySelection,
    ) -> OutboundChatMessage:
        category_buttons = tuple(
            (
                OutboundChatButton(
                    text=choice.name,
                    callback_data=ChatManualCategoryCallbackData.build_category_selection(
                        action_token=selection.action_token,
                        category_index=index,
                    ),
                ),
            )
            for index, choice in enumerate(selection.category_choices)
        )
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                f"{TelegramManualOperationPresenter.operation_type_label(selection.operation_type)}"
                "\n\n"
                f"Сумма: {selection.amount:.2f} {selection.currency}\n"
                f"Счет: {selection.account_name}\n\n"
                "Выбери категорию."
            ),
            buttons=category_buttons
            + ((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_manual_description_prompt(
        conversation: ChatConversation,
        description_input: StartedChatManualDescriptionInput,
    ) -> OutboundChatMessage:
        direction = TelegramManualOperationPresenter.account_direction(description_input)
        category = (
            f"\nКатегория: {description_input.category_name}"
            if description_input.category_name is not None
            else ""
        )
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                f"{TelegramManualOperationPresenter.operation_type_label(description_input.operation_type)}"
                "\n\n"
                f"Сумма: {description_input.amount:.2f} {description_input.currency}\n"
                f"Дата: {TelegramDatePresenter.format_date(description_input.operation_date)}\n"
                f"Счет: {direction}"
                f"{category}\n\n"
                "Описание? Можно пропустить."
            ),
            buttons=(
                (
                    OutboundChatButton(
                        text="⏭ Пропустить",
                        callback_data=ChatManualDescriptionCallbackData.build_skip_action(
                            action_token=description_input.action_token,
                        ),
                    ),
                ),
                (OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),
            ),
        )

    @staticmethod
    def show_manual_confirmation(
        conversation: ChatConversation,
        confirmation: ChatManualOperationConfirmation,
    ) -> OutboundChatMessage:
        operation_type_label = TelegramManualOperationPresenter.operation_type_label(
            confirmation.operation_type
        )
        destination = (
            f"\nКуда: {confirmation.destination_account_name}"
            if confirmation.destination_account_name is not None
            else ""
        )
        category = (
            f"\nКатегория: {confirmation.category_name}"
            if confirmation.category_name is not None
            else ""
        )
        description = (
            f"\nОписание: {confirmation.description}"
            if confirmation.description is not None
            else ""
        )
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "Проверь запись\n\n"
                f"Тип: {operation_type_label}\n"
                f"Сумма: {confirmation.amount:.2f} {confirmation.currency}\n"
                f"Дата: {TelegramDatePresenter.format_date(confirmation.operation_date)}\n"
                f"Счет: {confirmation.account_name}"
                f"{destination}"
                f"{category}"
                f"{description}"
            ),
            buttons=(
                (
                    OutboundChatButton(
                        text="✅ Записать",
                        callback_data=ChatManualConfirmationCallbackData.build_confirm_action(
                            action_token=confirmation.action_token,
                        ),
                    ),
                    OutboundChatButton(
                        text="✏️ Исправить",
                        callback_data=ChatManualCorrectionCallbackData.build_menu_action(
                            action_token=confirmation.action_token,
                        ),
                    ),
                ),
                (OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),
            ),
        )

    @staticmethod
    def show_manual_correction_menu(
        conversation: ChatConversation,
        selection: StartedChatManualCorrectionSelection,
    ) -> OutboundChatMessage:
        confirmation = selection.confirmation
        rows: list[tuple[OutboundChatButton, ...]] = [
            (
                OutboundChatButton(
                    text="💵 Сумма",
                    callback_data=ChatManualCorrectionCallbackData.build_amount_action(
                        action_token=selection.action_token,
                    ),
                ),
                OutboundChatButton(
                    text="📅 Дата",
                    callback_data=ChatManualCorrectionCallbackData.build_date_action(
                        action_token=selection.action_token,
                    ),
                ),
            ),
        ]
        if confirmation.operation_type != OperationType.TRANSFER:
            rows.append(
                (
                    OutboundChatButton(
                        text="🏷 Категория",
                        callback_data=ChatManualCorrectionCallbackData.build_category_action(
                            action_token=selection.action_token,
                        ),
                    ),
                )
            )
        rows.extend(
            (
                (
                    OutboundChatButton(
                        text="📝 Описание",
                        callback_data=ChatManualCorrectionCallbackData.build_description_action(
                            action_token=selection.action_token,
                        ),
                    ),
                ),
                (OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),
            )
        )
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "✏️ Что исправить?\n\n"
                f"Сумма: {confirmation.amount:.2f} {confirmation.currency}\n"
                f"Дата: {TelegramDatePresenter.format_date(confirmation.operation_date)}"
            ),
            buttons=tuple(rows),
        )

    @staticmethod
    def show_manual_operation_completed(
        conversation: ChatConversation,
        result: ChatManualOperationResult,
    ) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "✅ Операция записана\n\n"
                f"{TelegramManualOperationPresenter.operation_type_label(result.operation_type)}\n"
                f"Сумма: {result.amount:.2f} {result.currency}\n"
                f"Дата: {TelegramDatePresenter.format_date(result.operation_date)}"
            ),
            buttons=(
                (
                    OutboundChatButton(text="➕ Еще", callback_data="manual:start"),
                    OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),
                ),
            ),
        )

    @staticmethod
    def show_manual_operation_error(
        conversation: ChatConversation,
        message: str,
    ) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=f"⚠️ Не получилось записать операцию.\n\n{message}",
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_document_upload_account_menu(
        conversation: ChatConversation,
        upload: StartedChatDocumentUpload,
    ) -> OutboundChatMessage:
        buttons = tuple(
            (
                OutboundChatButton(
                    text=f"{account.name} / {account.currency}",
                    callback_data=ChatUploadCallbackData.build_account_selection(
                        action_token=upload.action_token,
                        account_index=index,
                    ),
                ),
            )
            for index, account in enumerate(upload.account_choices)
        )
        return OutboundChatMessage(
            conversation=conversation,
            text="📎 Выписка получена.\n\nВыбери счет для этого файла.",
            buttons=buttons + ((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_document_upload_completed(
        conversation: ChatConversation,
        document: UploadedDocument,
        review_url: str | None = None,
    ) -> OutboundChatMessage:
        status_label = TelegramImportStatusPresenter.status_label(document.status)
        buttons = [
            OutboundChatButton(text="🔎 Проверка", callback_data="review:next"),
            OutboundChatButton(text="📊 Статус", callback_data="status:show"),
        ]
        if review_url is not None:
            buttons.append(OutboundChatButton(text="🌐 Web", url=review_url))

        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "✅ Выписка загружена\n\n"
                f"📄 {document.original_filename}\n"
                f"Статус: {status_label}\n\n"
                "Проверь строки перед подтверждением."
            ),
            buttons=(tuple(buttons),),
        )

    @staticmethod
    def show_document_upload_error(
        conversation: ChatConversation,
        message: str,
    ) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=f"⚠️ Не получилось загрузить выписку.\n\n{message}",
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_unlinked_account_notice(
        conversation: ChatConversation,
        actor: ChatUser | None = None,
    ) -> OutboundChatMessage:
        telegram_hint = ""
        if actor is not None:
            telegram_hint = (
                "\n\n"
                f"Telegram ID для привязки: {actor.external_user_id}\n"
                "Открой Booker Tee в браузере и перейди на:\n"
                f"/chat-integrations/telegram/dev-link?external_user_id={actor.external_user_id}"
            )

        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "Сначала нужно подключить Telegram к пользователю Booker Tee.\n\n"
                "Пока аккаунт не привязан, бот не показывает финансовые данные и "
                "не записывает операции."
                f"{telegram_hint}"
            ),
            buttons=(
                (
                    OutboundChatButton(text="Подключить аккаунт", callback_data="link:start"),
                    OutboundChatButton(text="В меню", callback_data="main:menu"),
                ),
            ),
        )

    @staticmethod
    def show_safe_fallback(conversation: ChatConversation) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text="Нажми кнопку меню, так меньше шансов ошибиться.",
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )


class TelegramImportStatusPresenter:
    @staticmethod
    def status_label(status: UploadedDocumentStatus) -> str:
        match status:
            case UploadedDocumentStatus.PARSED:
                return "разобрано"
            case UploadedDocumentStatus.REQUIRES_REVIEW:
                return "требует проверки"
            case UploadedDocumentStatus.FAILED_TO_PARSE:
                return "не удалось разобрать"
            case UploadedDocumentStatus.UPLOADED:
                return "загружено"
            case _:
                return status.value


class TelegramManualOperationPresenter:
    @staticmethod
    def operation_type_label(operation_type: OperationType) -> str:
        match operation_type:
            case OperationType.EXPENSE:
                return "💸 Расход"
            case OperationType.INCOME:
                return "💰 Доход"
            case OperationType.TRANSFER:
                return "🔁 Перевод"
            case _:
                return operation_type.value

    @staticmethod
    def account_question(operation_type: OperationType) -> str:
        match operation_type:
            case OperationType.TRANSFER:
                return "Откуда перевести?"
            case OperationType.INCOME:
                return "Куда пришли деньги?"
            case OperationType.EXPENSE:
                return "Откуда ушли деньги?"
            case _:
                return "Выбери счет."

    @staticmethod
    def account_direction(
        selection: (
            StartedChatManualDateInput
            | StartedChatManualDateSelection
            | StartedChatManualDescriptionInput
        ),
    ) -> str:
        if selection.destination_account_name is None:
            return selection.account_name
        return f"{selection.account_name} → {selection.destination_account_name}"


class TelegramReviewQueueCardPresenter:
    @staticmethod
    def format_item(item: ChatReviewQueueItem) -> str:
        return (
            "🔎 Проверка Booker Tee\n\n"
            f"📍 Строка: {TelegramReviewQueueCardPresenter.row_position_label(item)}\n"
            f"{TelegramReviewQueueCardPresenter.remaining_line(item)}"
            f"📅 Дата: {TelegramReviewQueueCardPresenter.date_label(item)}\n"
            f"🏦 Счет: {item.account_name or 'не выбран'}\n"
            f"💵 Сумма: {TelegramReviewQueueCardPresenter.amount_label(item)}\n"
            f"📝 Описание: {item.description or 'нет описания'}\n\n"
            f"⚠️ Статус: {TelegramReviewQueueCardPresenter.status_label(item)}\n"
            f"🧭 Похоже на: {TelegramReviewQueueCardPresenter.operation_type_label(item)}\n"
            f"{TelegramReviewQueueCardPresenter.suggestion_line(item)}"
            f"👉 Что сделать: {TelegramReviewQueueCardPresenter.action_hint(item)}"
            f"{TelegramReviewQueueCardPresenter.error_suffix(item)}"
        )

    @staticmethod
    def row_position_label(item: ChatReviewQueueItem) -> str:
        current_position = item.row_index + 1
        if item.document_row_count is None:
            return str(current_position)
        return f"{current_position} из {item.document_row_count}"

    @staticmethod
    def remaining_line(item: ChatReviewQueueItem) -> str:
        if item.document_reviewable_count is None:
            return ""
        return f"⏳ Осталось проверить: {item.document_reviewable_count}\n"

    @staticmethod
    def date_label(item: ChatReviewQueueItem) -> str:
        if item.operation_date is None:
            return "не распознана"
        return TelegramDatePresenter.format_date(item.operation_date)

    @staticmethod
    def amount_label(item: ChatReviewQueueItem) -> str:
        if item.amount is not None:
            return f"{item.amount:.2f} {item.currency or ''}".strip()
        return (
            " ".join(part for part in [item.amount_raw, item.currency] if part) or "не распознана"
        )

    @staticmethod
    def status_label(item: ChatReviewQueueItem) -> str:
        match item.status:
            case "needs_review":
                return "нужно проверить"
            case "possible_duplicate":
                return "возможный дубль"
            case "failed":
                return "не удалось распознать"
            case "normalized":
                return "распознано"
            case "suggested":
                return "есть предложение"
            case "matched":
                return "помечено как уникальная"
            case _:
                return item.status

    @staticmethod
    def operation_type_label(item: ChatReviewQueueItem) -> str:
        match item.suggested_operation_type:
            case "income":
                return "доход"
            case "expense":
                return "расход"
            case "transfer":
                return "перевод между счетами"
            case "adjustment":
                return "корректировка"
            case _:
                return "нужно выбрать"

    @staticmethod
    def suggestion_line(item: ChatReviewQueueItem) -> str:
        parts = []
        operation_type = TelegramReviewQueueCardPresenter.operation_type_label(item)
        if operation_type != "нужно выбрать":
            parts.append(operation_type)
        if item.suggested_category_name is not None:
            parts.append(item.suggested_category_name)
        if not parts:
            return ""
        return f"💡 Предложение: {' · '.join(parts)}\n"

    @staticmethod
    def action_hint(item: ChatReviewQueueItem) -> str:
        match item.status:
            case "possible_duplicate":
                return "проверь: это дубль или не дубль"
            case "failed":
                return "лучше открыть в Booker Tee и исправить вручную"
            case _:
                return "выбери категорию, перевод или не учитывай"

    @staticmethod
    def error_suffix(item: ChatReviewQueueItem) -> str:
        if not item.normalization_error:
            return ""
        return f"\n\n❗ Почему нужно проверить: {item.normalization_error}"


class TelegramReviewTransferChoicePresenter:
    @staticmethod
    def pair_button_text(pair: ChatReviewTransferPairChoice) -> str:
        date_label = (
            TelegramDatePresenter.format_date(pair.operation_date)
            if pair.operation_date is not None
            else "дата?"
        )
        amount_label = TelegramReviewTransferChoicePresenter.amount_label(pair)
        account_label = pair.account_name or "счет?"
        return f"Пара: {account_label} / {date_label} / {amount_label}"

    @staticmethod
    def amount_label(pair: ChatReviewTransferPairChoice) -> str:
        if pair.amount is None:
            return "сумма?"
        return f"{pair.amount:.2f} {pair.currency or ''}".strip()


class TelegramReviewActionErrorPresenter:
    @staticmethod
    def is_stale_button_error(message: str) -> bool:
        return message.startswith("This review action expired.") or message == (
            "Stored review action is invalid."
        )
