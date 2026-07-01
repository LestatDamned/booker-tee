from app.features.chat_integrations.actions.workspace import ChatWorkspaceCallbackData
from app.features.chat_integrations.schemas import (
    ChatConversation,
    OutboundChatButton,
    OutboundChatDeliveryMode,
    OutboundChatMessage,
)
from app.features.chat_integrations.use_cases.workspace import StartedChatWorkspaceSelection

CHAT_MAIN_MENU_BUTTON_TEXT = "🏠 Меню"
CHAT_WORKSPACE_BUTTON_TEXT = "🗂️ Пространство"
CHAT_WORKSPACE_TITLE = "🗂️ Рабочее пространство"
CHAT_WORKSPACE_CHOICE_PREFIX = "🗂️ "


class TelegramWorkspacePresenter:
    @staticmethod
    def format_label(workspace_name: str) -> str:
        return f"{CHAT_WORKSPACE_CHOICE_PREFIX}{workspace_name}"

    @staticmethod
    def show_menu(
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
    def show_switch_error(
        conversation: ChatConversation,
        message: str,
    ) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=f"⚠️ Не получилось переключить пространство.\n\n{message}",
            buttons=(
                (
                    OutboundChatButton(
                        text=CHAT_WORKSPACE_BUTTON_TEXT,
                        callback_data="workspace:choose",
                    ),
                    OutboundChatButton(
                        text=CHAT_MAIN_MENU_BUTTON_TEXT,
                        callback_data="main:menu",
                    ),
                ),
            ),
            delivery_mode=OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE,
            callback_notification="Не получилось",
        )
