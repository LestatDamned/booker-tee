from app.features.chat_integrations.presentation.workspace import (
    CHAT_WORKSPACE_BUTTON_TEXT,
    TelegramWorkspacePresenter,
)
from app.features.chat_integrations.schemas import (
    ChatConversation,
    ChatUser,
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
