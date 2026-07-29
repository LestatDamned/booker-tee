from app.features.chat_integrations.actions.upload import ChatUploadCallbackData
from app.features.chat_integrations.application import StartedChatDocumentUpload
from app.features.chat_integrations.schemas import (
    ChatConversation,
    OutboundChatButton,
    OutboundChatMessage,
)
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.models import UploadedDocument


class TelegramUploadPresenter:
    @staticmethod
    def show_not_ready(conversation: ChatConversation) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "⚠️ Загрузка временно недоступна.\n\nПопробуй позже или открой импорт в Booker Tee."
            ),
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )

    @staticmethod
    def show_instructions(conversation: ChatConversation) -> OutboundChatMessage:
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
    def show_account_menu(
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
    def show_completed(
        conversation: ChatConversation,
        document: UploadedDocument,
        review_url: str | None = None,
    ) -> OutboundChatMessage:
        status_label = TelegramUploadStatusPresenter.status_label(document.status)
        buttons = [
            OutboundChatButton(text="🔎 Проверка", callback_data="review:choose"),
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
    def show_error(
        conversation: ChatConversation,
        message: str,
    ) -> OutboundChatMessage:
        return OutboundChatMessage(
            conversation=conversation,
            text=f"⚠️ Не получилось загрузить выписку.\n\n{message}",
            buttons=((OutboundChatButton(text="🏠 Меню", callback_data="main:menu"),),),
        )


class TelegramUploadStatusPresenter:
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
