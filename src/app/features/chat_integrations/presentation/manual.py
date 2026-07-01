from app.features.chat_integrations.actions.manual import (
    ChatManualAccountCallbackData,
    ChatManualCategoryCallbackData,
    ChatManualCategoryPageCallbackData,
    ChatManualConfirmationCallbackData,
    ChatManualCorrectionCallbackData,
    ChatManualDateCallbackData,
    ChatManualDescriptionCallbackData,
)
from app.features.chat_integrations.presentation.formatting import TelegramDatePresenter
from app.features.chat_integrations.schemas import (
    ChatConversation,
    OutboundChatButton,
    OutboundChatDeliveryMode,
    OutboundChatMessage,
)
from app.features.chat_integrations.use_cases.manual.dto import (
    ChatManualOperationConfirmation,
    ChatManualOperationResult,
    StartedChatManualAccountSelection,
    StartedChatManualAmountInput,
    StartedChatManualCategorySelection,
    StartedChatManualCorrectionSelection,
    StartedChatManualDateInput,
    StartedChatManualDateSelection,
    StartedChatManualDescriptionInput,
)
from app.features.ledger.models import OperationType


class TelegramManualPresenter:
    @staticmethod
    def _show_manual_workspace(
        *,
        conversation: ChatConversation,
        text: str,
        buttons: tuple[tuple[OutboundChatButton, ...], ...],
        target_message_id: str | None = None,
    ) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=text,
            buttons=buttons,
            delivery_mode=OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE,
            target_message_id=target_message_id,
        )

    @staticmethod
    def show_type_menu(conversation: ChatConversation) -> OutboundChatMessage:
        return TelegramManualPresenter._show_manual_workspace(
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
    def show_account_menu(
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
        return TelegramManualPresenter._show_manual_workspace(
            conversation=conversation,
            text=(
                f"{TelegramManualOperationPresenter.operation_type_label(selection.operation_type)}"
                f"{source_hint}\n\n"
                f"{question}"
            ),
            buttons=account_buttons
            + ((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
            target_message_id=selection.source_message_id,
        )

    @staticmethod
    def show_amount_prompt(
        conversation: ChatConversation,
        amount_input: StartedChatManualAmountInput,
    ) -> OutboundChatMessage:
        direction = (
            f"{amount_input.account_name} → {amount_input.destination_account_name}"
            if amount_input.destination_account_name is not None
            else amount_input.account_name
        )
        return TelegramManualPresenter._show_manual_workspace(
            conversation=conversation,
            text=(
                f"{TelegramManualOperationPresenter.operation_type_label(amount_input.operation_type)}"
                f"\n\nСчет: {direction}\n"
                f"Валюта: {amount_input.currency}\n\n"
                "Напиши сумму одним числом.\n"
                "Например: 1250 или 1 250,50"
            ),
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
            target_message_id=amount_input.source_message_id,
        )

    @staticmethod
    def show_amount_error(
        conversation: ChatConversation,
        message: str,
    ) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=f"⚠️ {message}\n\nНапиши только сумму. Например: 1250",
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_date_menu(
        conversation: ChatConversation,
        selection: StartedChatManualDateSelection,
    ) -> OutboundChatMessage:
        direction = TelegramManualOperationPresenter.account_direction(selection)
        return TelegramManualPresenter._show_manual_workspace(
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
            target_message_id=selection.source_message_id,
        )

    @staticmethod
    def show_date_input_prompt(
        conversation: ChatConversation,
        date_input: StartedChatManualDateInput,
    ) -> OutboundChatMessage:
        direction = TelegramManualOperationPresenter.account_direction(date_input)
        return TelegramManualPresenter._show_manual_workspace(
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
            target_message_id=date_input.source_message_id,
        )

    @staticmethod
    def show_date_error(
        conversation: ChatConversation,
        message: str,
    ) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=f"⚠️ {message}\n\nНапиши дату. Например: 30.06.2026",
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_category_menu(
        conversation: ChatConversation,
        selection: StartedChatManualCategorySelection,
    ) -> OutboundChatMessage:
        category_buttons = tuple(
            (
                OutboundChatButton(
                    text=choice.name,
                    callback_data=ChatManualCategoryCallbackData.build_category_selection(
                        action_token=selection.action_token,
                        category_index=selection.page_start_index + index,
                    ),
                ),
            )
            for index, choice in enumerate(selection.category_choices)
        )
        page_buttons: list[OutboundChatButton] = []
        if selection.page_index > 0:
            page_buttons.append(
                OutboundChatButton(
                    text="⬅️ Пред.",
                    callback_data=ChatManualCategoryPageCallbackData.build_page_action(
                        action_token=selection.action_token,
                        page_index=selection.page_index - 1,
                    ),
                )
            )
        if selection.page_index + 1 < selection.page_count:
            page_buttons.append(
                OutboundChatButton(
                    text="➡️ Еще",
                    callback_data=ChatManualCategoryPageCallbackData.build_page_action(
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
        return TelegramManualPresenter._show_manual_workspace(
            conversation=conversation,
            text=(
                f"{TelegramManualOperationPresenter.operation_type_label(selection.operation_type)}"
                "\n\n"
                f"Сумма: {selection.amount:.2f} {selection.currency}\n"
                f"Счет: {selection.account_name}\n\n"
                f"Выбери категорию.{page_hint}"
            ),
            buttons=category_buttons
            + page_row
            + ((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
            target_message_id=selection.source_message_id,
        )

    @staticmethod
    def show_description_prompt(
        conversation: ChatConversation,
        description_input: StartedChatManualDescriptionInput,
    ) -> OutboundChatMessage:
        direction = TelegramManualOperationPresenter.account_direction(description_input)
        category = (
            f"\nКатегория: {description_input.category_name}"
            if description_input.category_name is not None
            else ""
        )
        return TelegramManualPresenter._show_manual_workspace(
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
            target_message_id=description_input.source_message_id,
        )

    @staticmethod
    def show_confirmation(
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
        return TelegramManualPresenter._show_manual_workspace(
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
            target_message_id=confirmation.source_message_id,
        )

    @staticmethod
    def show_correction_menu(
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
        return TelegramManualPresenter._show_manual_workspace(
            conversation=conversation,
            text=(
                "✏️ Что исправить?\n\n"
                f"Сумма: {confirmation.amount:.2f} {confirmation.currency}\n"
                f"Дата: {TelegramDatePresenter.format_date(confirmation.operation_date)}"
            ),
            buttons=tuple(rows),
            target_message_id=selection.confirmation.source_message_id,
        )

    @staticmethod
    def show_completed(
        conversation: ChatConversation,
        result: ChatManualOperationResult,
    ) -> OutboundChatMessage:
        return TelegramManualPresenter._show_manual_workspace(
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
    def show_error(
        conversation: ChatConversation,
        message: str,
    ) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=f"⚠️ Не получилось записать операцию.\n\n{message}",
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )


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
