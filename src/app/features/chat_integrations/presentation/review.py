from app.features.chat_integrations.actions.review import (
    ChatReviewActionConfirmationCallbackData,
    ChatReviewCallbackData,
    ChatReviewCategoryCallbackData,
    ChatReviewCategoryPageCallbackData,
    ChatReviewDocumentCallbackData,
    ChatReviewNavigationCallbackData,
    ChatReviewPropertyCallbackData,
    ChatReviewReturnCallbackData,
    ChatReviewRulePatternCallbackData,
    ChatReviewRuleSuggestionCallbackData,
    ChatReviewTransferCallbackData,
    ChatReviewTransferConfirmationCallbackData,
    ChatReviewTransferExistingCallbackData,
    ChatReviewTransferPairCallbackData,
)
from app.features.chat_integrations.presentation.formatting import TelegramDatePresenter
from app.features.chat_integrations.schemas import (
    ChatConversation,
    OutboundChatButton,
    OutboundChatDeliveryMode,
    OutboundChatMessage,
)
from app.features.chat_integrations.use_cases.review.dto import (
    ChatReviewDocumentChoice,
    ChatReviewExistingTransferChoice,
    ChatReviewNavigationBoundary,
    ChatReviewQueueItem,
    ChatReviewTransferPairChoice,
    ChatReviewTransferPreviewEntry,
    StartedChatReviewActionConfirmation,
    StartedChatReviewCategorySelection,
    StartedChatReviewDocumentSelection,
    StartedChatReviewPropertySelection,
    StartedChatReviewRulePatternInput,
    StartedChatReviewRulePatternSelection,
    StartedChatReviewRuleSuggestion,
    StartedChatReviewTransferConfirmation,
    StartedChatReviewTransferSelection,
)


class TelegramReviewPresenter:
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
    def show_next_item(
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
        navigation_rows.append(
            (OutboundChatButton(text="📄 Выписки", callback_data="review:choose"),)
        )
        navigation_rows.append((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),))

        return TelegramReviewPresenter._show_review_workspace(
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
    def show_document_selection(
        conversation: ChatConversation,
        selection: StartedChatReviewDocumentSelection,
    ) -> OutboundChatMessage:
        document_buttons = tuple(
            (
                OutboundChatButton(
                    text=TelegramReviewDocumentChoicePresenter.button_text(choice),
                    callback_data=ChatReviewDocumentCallbackData.build_document_selection(
                        action_token=selection.action_token,
                        document_index=index,
                    ),
                ),
            )
            for index, choice in enumerate(selection.document_choices)
        )
        document_lines = "\n".join(
            TelegramReviewDocumentChoicePresenter.summary_line(index, choice)
            for index, choice in enumerate(selection.document_choices, start=1)
        )
        return TelegramReviewPresenter._show_review_workspace(
            conversation=conversation,
            text=(
                "🔎 Проверка выписки\n\n"
                f"{document_lines}\n\n"
                "Выбери выписку, которую сейчас проверяем."
            ),
            buttons=document_buttons
            + ((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_action_confirmation(
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

        return TelegramReviewPresenter._show_review_workspace(
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
    def show_navigation_boundary(
        conversation: ChatConversation,
        boundary: ChatReviewNavigationBoundary,
    ) -> OutboundChatMessage:
        text = (
            "Это первая строка в выписке."
            if boundary.direction == "prev"
            else "Это последняя строка в выписке."
        )
        return TelegramReviewPresenter._show_review_workspace(
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
    def show_category_menu(
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
        return TelegramReviewPresenter._show_review_workspace(
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
    def show_property_menu(
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
        return TelegramReviewPresenter._show_review_workspace(
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
    def show_transfer_account_menu(
        conversation: ChatConversation,
        selection: StartedChatReviewTransferSelection,
    ) -> OutboundChatMessage:
        existing_buttons = tuple(
            (
                OutboundChatButton(
                    text=TelegramReviewTransferChoicePresenter.existing_button_text(transfer),
                    callback_data=ChatReviewTransferExistingCallbackData.build_existing_selection(
                        action_token=selection.action_token,
                        transfer_index=index,
                    ),
                ),
            )
            for index, transfer in enumerate(selection.existing_transfer_choices)
        )
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
                    text=f"Создать: {account.name} / {account.currency}",
                    callback_data=ChatReviewTransferCallbackData.build_account_selection(
                        action_token=selection.action_token,
                        account_index=index,
                    ),
                ),
            )
            for index, account in enumerate(selection.account_choices)
        )
        return TelegramReviewPresenter._show_review_workspace(
            conversation=conversation,
            text=(
                "Выбери, как оформить перевод.\n\n"
                "Сначала лучше привязать строку к уже созданному переводу или парной строке. "
                "Если совпадений нет - выбери второй счет и создай новый перевод.\n\n"
                f"{TelegramReviewQueueCardPresenter.format_item(selection.item)}"
            ),
            buttons=existing_buttons
            + pair_buttons
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
    def show_transfer_confirmation(
        conversation: ChatConversation,
        confirmation: StartedChatReviewTransferConfirmation,
    ) -> OutboundChatMessage:
        transfer_preview = TelegramReviewTransferChoicePresenter.confirmation_preview(confirmation)
        return TelegramReviewPresenter._show_review_workspace(
            conversation=conversation,
            text=(
                "🔁 Подтвердить перевод?\n\n"
                f"{transfer_preview}"
                "Перевод не попадет в доходы или расходы.\n\n"
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
    def show_rule_suggestion(
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
        return TelegramReviewPresenter._show_review_workspace(
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
    def show_rule_pattern_input(
        conversation: ChatConversation,
        selection: StartedChatReviewRulePatternInput,
    ) -> OutboundChatMessage:
        return TelegramReviewPresenter._show_review_workspace(
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
    def show_rule_pattern_menu(
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
        return TelegramReviewPresenter._show_review_workspace(
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
    def show_queue_empty(
        conversation: ChatConversation,
        callback_notification: str | None = "Готово",
    ) -> OutboundChatMessage:
        return TelegramReviewPresenter._show_review_workspace(
            conversation=conversation,
            text=(
                "✅ Сейчас нет строк для проверки.\n\n"
                "Если в меню есть документы, им нужен разбор выписки или повторный импорт."
            ),
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
            callback_notification=callback_notification,
        )

    @staticmethod
    def show_action_applied(
        conversation: ChatConversation,
        action_label: str,
    ) -> OutboundChatMessage:
        return TelegramReviewPresenter._show_review_workspace(
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
    def show_action_error(
        conversation: ChatConversation,
        message: str,
    ) -> OutboundChatMessage:
        if TelegramReviewActionErrorPresenter.is_stale_button_error(message):
            return TelegramReviewPresenter.show_stale_button_error(conversation)

        return TelegramReviewPresenter._show_review_workspace(
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
    def show_stale_button_error(conversation: ChatConversation) -> OutboundChatMessage:
        return TelegramReviewPresenter._show_review_workspace(
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


class TelegramReviewQueueCardPresenter:
    @staticmethod
    def format_item(item: ChatReviewQueueItem) -> str:
        return (
            "🔎 Проверка Booker Tee\n\n"
            f"{TelegramReviewQueueCardPresenter.document_line(item)}"
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
    def document_line(item: ChatReviewQueueItem) -> str:
        if item.document_label is None:
            return ""
        return f"📄 Выписка: {item.document_label}\n"

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


class TelegramReviewDocumentChoicePresenter:
    BUTTON_TEXT_LIMIT = 48

    @staticmethod
    def button_text(choice: ChatReviewDocumentChoice) -> str:
        label = choice.label
        count = choice.reviewable_count
        text = f"📄 {label} ({count})"
        if len(text) <= TelegramReviewDocumentChoicePresenter.BUTTON_TEXT_LIMIT:
            return text
        return f"{text[:45]}..."

    @staticmethod
    def summary_line(index: int, choice: ChatReviewDocumentChoice) -> str:
        return f"{index}. {choice.label} - к проверке: {choice.reviewable_count}"


class TelegramReviewTransferChoicePresenter:
    @staticmethod
    def confirmation_preview(confirmation: StartedChatReviewTransferConfirmation) -> str:
        if not confirmation.preview_entries:
            return f"Цель: {confirmation.target_label}\n\n"
        lines = [
            TelegramReviewTransferChoicePresenter.preview_entry_line(entry)
            for entry in confirmation.preview_entries
        ]
        return "Проводки:\n" + "\n".join(lines) + "\n\n"

    @staticmethod
    def preview_entry_line(entry: ChatReviewTransferPreviewEntry) -> str:
        sign = "+" if entry.amount > 0 else ""
        amount = f"{sign}{entry.amount:.2f} {entry.currency or ''}".strip()
        return f"• {entry.account_name}: {amount}"

    @staticmethod
    def existing_button_text(transfer: ChatReviewExistingTransferChoice) -> str:
        date_label = TelegramDatePresenter.format_date(transfer.operation_date)
        counterparty_label = transfer.counterparty_account_name or "второй счет?"
        amount_label = "сумма?"
        if transfer.counterparty_amount is not None:
            amount_label = (
                f"{transfer.counterparty_amount:.2f} {transfer.counterparty_currency or ''}"
            ).strip()
        return f"Созданный: {counterparty_label} / {date_label} / {amount_label}"

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
