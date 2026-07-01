from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.handlers.dashboard import ChatDashboardEventHandler
from app.features.chat_integrations.handlers.manual import ChatManualEventHandler
from app.features.chat_integrations.handlers.review_actions import ChatReviewActionHandler
from app.features.chat_integrations.handlers.review_confirmation import (
    ChatReviewConfirmationHandler,
)
from app.features.chat_integrations.handlers.review_queue import ChatReviewQueueHandler
from app.features.chat_integrations.handlers.review_rule_suggestion import (
    ChatReviewRuleSuggestionHandler,
)
from app.features.chat_integrations.handlers.review_transfer import ChatReviewTransferHandler
from app.features.chat_integrations.handlers.upload import ChatUploadEventHandler
from app.features.chat_integrations.handlers.workspace import ChatWorkspaceEventHandler
from app.features.chat_integrations.providers.base import ChatDocumentDownloader, ChatProvider


class ChatEventHandlers:
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

    def upload(self) -> ChatUploadEventHandler:
        return ChatUploadEventHandler(
            self.session,
            self.settings,
            self.document_downloader,
            self.chat_provider,
        )

    def dashboard(self) -> ChatDashboardEventHandler:
        return ChatDashboardEventHandler(self.session)

    def workspace(self) -> ChatWorkspaceEventHandler:
        return ChatWorkspaceEventHandler(self.session, self.settings)

    def manual(self) -> ChatManualEventHandler:
        return ChatManualEventHandler(self.session)

    def review_action(self) -> ChatReviewActionHandler:
        return ChatReviewActionHandler(self.session, self.settings)

    def review_confirmation(self) -> ChatReviewConfirmationHandler:
        return ChatReviewConfirmationHandler(self.session, self.settings)

    def review_queue(self) -> ChatReviewQueueHandler:
        return ChatReviewQueueHandler(self.session, self.settings)

    def review_rule_suggestion(self) -> ChatReviewRuleSuggestionHandler:
        return ChatReviewRuleSuggestionHandler(self.session, self.settings)

    def review_transfer(self) -> ChatReviewTransferHandler:
        return ChatReviewTransferHandler(self.session, self.settings)
