from dataclasses import dataclass

from app.features.chat_integrations.schemas import (
    ChatConversation,
    OutboundChatButton,
    OutboundChatMessage,
)
from app.features.imports.documents.types import UploadedDocumentStatus


@dataclass(frozen=True)
class ImportDocumentUploadedNotification:
    workspace_name: str
    document_status: UploadedDocumentStatus
    review_url: str | None = None


class ChatImportNotificationFormatter:
    @staticmethod
    def format_document_uploaded(
        conversation: ChatConversation,
        notification: ImportDocumentUploadedNotification,
    ) -> OutboundChatMessage:
        status_label = ChatImportNotificationStatusPresenter.status_label(
            notification.document_status
        )
        buttons: tuple[tuple[OutboundChatButton, ...], ...] = ()
        if notification.review_url is not None:
            buttons = (
                (OutboundChatButton(text="Открыть Booker Tee", url=notification.review_url),),
            )

        return OutboundChatMessage(
            conversation=conversation,
            text=(
                "Booker Tee\n\n"
                f"Workspace: {notification.workspace_name}\n"
                "Загружена выписка.\n"
                f"Статус: {status_label}\n\n"
                "Подробности доступны только в Booker Tee."
            ),
            buttons=buttons,
        )


class ChatImportNotificationStatusPresenter:
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
            case UploadedDocumentStatus.PENDING_PARSE:
                return "ожидает разбора"
            case _:
                return status.value
