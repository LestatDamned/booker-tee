from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.actions.upload import ChatUploadAccountSelection
from app.features.chat_integrations.application import (
    ChatDocumentUploadService,
    ChatReviewUrlBuilder,
)
from app.features.chat_integrations.errors import ChatDocumentUploadError
from app.features.chat_integrations.notifications.dispatcher import (
    ChatNotificationProviderRegistry,
    ChatSharedFeedNotificationService,
)
from app.features.chat_integrations.presentation.upload import TelegramUploadPresenter
from app.features.chat_integrations.providers.base import ChatDocumentDownloader, ChatProvider
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace
from app.features.imports.documents.commands.upload import StatementUploadResult


class ChatUploadEventHandler:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None,
        document_downloader: ChatDocumentDownloader | None,
        chat_provider: ChatProvider | None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.document_downloader = document_downloader
        self.chat_provider = chat_provider

    async def start_document_upload(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        if self.settings is None or self.document_downloader is None:
            return TelegramUploadPresenter.show_not_ready(event.conversation)

        try:
            upload = await ChatDocumentUploadService(
                self.session,
                self.settings,
                self.document_downloader,
            ).start_document_upload(
                context=bound_workspace.context,
                document=event.document,
            )
        except ChatDocumentUploadError as exc:
            return TelegramUploadPresenter.show_error(
                event.conversation,
                str(exc),
            )

        return TelegramUploadPresenter.show_account_menu(
            event.conversation,
            upload,
        )

    async def complete_document_upload(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        account_selection: ChatUploadAccountSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        if self.settings is None or self.document_downloader is None:
            return TelegramUploadPresenter.show_not_ready(event.conversation)

        try:
            upload = await ChatDocumentUploadService(
                self.session,
                self.settings,
                self.document_downloader,
            ).complete_document_upload(
                context=bound_workspace.context,
                action_token=account_selection.action_token,
                account_index=account_selection.account_index,
            )
        except ChatDocumentUploadError as exc:
            return TelegramUploadPresenter.show_error(
                event.conversation,
                str(exc),
            )

        await self._notify_shared_feed_about_uploaded_document(event, bound_workspace, upload)
        return TelegramUploadPresenter.show_completed(
            event.conversation,
            upload,
            ChatReviewUrlBuilder.build_document_review_url(
                self.settings,
                upload.document_id,
            ),
        )

    async def _notify_shared_feed_about_uploaded_document(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        upload: StatementUploadResult,
    ) -> None:
        if self.chat_provider is None:
            return

        await ChatSharedFeedNotificationService(
            session=self.session,
            settings=self.settings,
            provider_registry=ChatNotificationProviderRegistry(
                {event.provider: self.chat_provider}
            ),
        ).notify_import_document_uploaded(
            context=bound_workspace.context,
            document_id=upload.document_id,
            document_status=upload.document_status,
        )
