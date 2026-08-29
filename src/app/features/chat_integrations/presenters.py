from app.features.chat_integrations.presentation.workspace import (
    CHAT_WORKSPACE_BUTTON_TEXT,
    TelegramWorkspacePresenter,
)
from app.features.chat_integrations.schemas import (
    ChatConversation,
    OutboundChatButton,
    OutboundChatMessage,
)
from app.features.chat_integrations.use_cases.dashboard import (
    ChatPrivateStatus,
)
from app.features.workspaces.service import WorkspaceContext


class TelegramMainMenuPresenter:
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
                OutboundChatButton(text="🔎 Проверка", callback_data="review:choose"),
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
                f"📄 Документы: {status.documents_needing_attention}\n"
                f"🔎 К проверке: {status.raw_transactions_needing_attention}\n\n"
                "📎 Выписку можно отправить файлом в этот чат."
            ),
            buttons=tuple(button_rows),
            callback_notification=callback_notification,
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
    def show_unlinked_account_notice(
        conversation: ChatConversation,
        link_url: str | None = None,
    ) -> OutboundChatMessage:
        buttons = [OutboundChatButton(text="В меню", callback_data="main:menu")]
        if link_url is not None:
            buttons.insert(0, OutboundChatButton(text="Подключить аккаунт", url=link_url))

        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "Сначала нужно подключить Telegram к пользователю Booker Tee.\n\n"
                "Пока аккаунт не привязан, бот не показывает финансовые данные и "
                "не записывает операции. Открой Booker Tee, получи одноразовый код "
                "и отправь его командой /link КОД."
            ),
            buttons=(tuple(buttons),),
        )

    @staticmethod
    def show_link_success(conversation: ChatConversation) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text="✅ Telegram подключён. Отправь /start, чтобы открыть меню Booker Tee.",
        )

    @staticmethod
    def show_link_failure(conversation: ChatConversation, message: str) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation, text=f"Не удалось подключить: {message}"
        )

    @staticmethod
    def show_safe_fallback(conversation: ChatConversation) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text="Нажми кнопку меню, так меньше шансов ошибиться.",
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )
