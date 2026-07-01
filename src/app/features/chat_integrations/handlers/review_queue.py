from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.actions.review import (
    ChatReviewDocumentSelection,
    ChatReviewNavigationSelection,
    ChatReviewReturnSelection,
)
from app.features.chat_integrations.application import ChatReviewUrlBuilder
from app.features.chat_integrations.errors import ChatReviewActionError
from app.features.chat_integrations.presentation.review import TelegramReviewPresenter
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.review.dto import (
    ChatReviewContinuationAnchor,
    ChatReviewNavigationBoundary,
)
from app.features.chat_integrations.use_cases.review.queue import ChatReviewQueueService
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


class ChatReviewQueueHandler:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None,
    ) -> None:
        self.session = session
        self.settings = settings

    async def show_document_selection(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        selection = await ChatReviewQueueService(self.session).start_document_selection(
            bound_workspace.context
        )
        if selection is None:
            return TelegramReviewPresenter.show_queue_empty(event.conversation)

        return TelegramReviewPresenter.show_document_selection(event.conversation, selection)

    async def show_selected_document_item(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatReviewDocumentSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        try:
            started_item = await ChatReviewQueueService(
                self.session
            ).start_selected_document_review_item(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )
        if started_item is None:
            return TelegramReviewPresenter.show_queue_empty(event.conversation)

        return TelegramReviewPresenter.show_next_item(
            event.conversation,
            started_item.item,
            started_item.action_token,
            ChatReviewUrlBuilder.build_raw_transaction_review_url(
                self.settings,
                document_id=started_item.item.document_id,
                raw_transaction_id=started_item.item.raw_transaction_id,
            ),
        )

    async def show_next_item(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        started_item = await ChatReviewQueueService(self.session).start_next_review_item(
            bound_workspace.context
        )
        if started_item is None:
            return TelegramReviewPresenter.show_queue_empty(event.conversation)

        return TelegramReviewPresenter.show_next_item(
            event.conversation,
            started_item.item,
            started_item.action_token,
            ChatReviewUrlBuilder.build_raw_transaction_review_url(
                self.settings,
                document_id=started_item.item.document_id,
                raw_transaction_id=started_item.item.raw_transaction_id,
            ),
        )

    async def show_next_item_after_success(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        action_label: str,
        continuation_anchor: ChatReviewContinuationAnchor | None = None,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        callback_notification = f"Готово: {action_label}"
        review_queue = ChatReviewQueueService(self.session)
        if continuation_anchor is None:
            started_item = await review_queue.start_next_review_item(bound_workspace.context)
        else:
            started_item = await review_queue.start_next_review_item_after(
                context=bound_workspace.context,
                anchor=continuation_anchor,
            )
        if started_item is None:
            return TelegramReviewPresenter.show_queue_empty(
                event.conversation,
                callback_notification=callback_notification,
            )

        return TelegramReviewPresenter.show_next_item(
            event.conversation,
            started_item.item,
            started_item.action_token,
            ChatReviewUrlBuilder.build_raw_transaction_review_url(
                self.settings,
                document_id=started_item.item.document_id,
                raw_transaction_id=started_item.item.raw_transaction_id,
            ),
            callback_notification=callback_notification,
        )

    async def return_to_item(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatReviewReturnSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        try:
            started_item = await ChatReviewQueueService(self.session).return_to_review_item(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramReviewPresenter.show_next_item(
            event.conversation,
            started_item.item,
            started_item.action_token,
            ChatReviewUrlBuilder.build_raw_transaction_review_url(
                self.settings,
                document_id=started_item.item.document_id,
                raw_transaction_id=started_item.item.raw_transaction_id,
            ),
        )

    async def navigate_item(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatReviewNavigationSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        try:
            result = await ChatReviewQueueService(self.session).start_adjacent_review_item(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        if isinstance(result, ChatReviewNavigationBoundary):
            return TelegramReviewPresenter.show_navigation_boundary(
                event.conversation,
                result,
            )

        return TelegramReviewPresenter.show_next_item(
            event.conversation,
            result.item,
            result.action_token,
            ChatReviewUrlBuilder.build_raw_transaction_review_url(
                self.settings,
                document_id=result.item.document_id,
                raw_transaction_id=result.item.raw_transaction_id,
            ),
        )
