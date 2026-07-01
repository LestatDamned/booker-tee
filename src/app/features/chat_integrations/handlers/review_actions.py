from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.actions.review import (
    ChatReviewActionConfirmationSelection,
    ChatReviewActionSelection,
    ChatReviewCallbackData,
)
from app.features.chat_integrations.errors import ChatReviewActionError
from app.features.chat_integrations.handlers.review_confirmation import (
    ChatReviewConfirmationHandler,
)
from app.features.chat_integrations.handlers.review_queue import ChatReviewQueueHandler
from app.features.chat_integrations.handlers.review_transfer import ChatReviewTransferHandler
from app.features.chat_integrations.presentation.review import TelegramReviewPresenter
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.review.actions import ChatReviewActionService
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


class ChatReviewActionHandler:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None,
    ) -> None:
        self.session = session
        self.settings = settings

    def _confirmation_handler(self) -> ChatReviewConfirmationHandler:
        return ChatReviewConfirmationHandler(self.session, self.settings)

    def _queue_handler(self) -> ChatReviewQueueHandler:
        return ChatReviewQueueHandler(self.session, self.settings)

    def _transfer_handler(self) -> ChatReviewTransferHandler:
        return ChatReviewTransferHandler(self.session, self.settings)

    async def apply_action(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        review_action: ChatReviewActionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        if review_action.action == ChatReviewCallbackData.CONFIRM_ACTION:
            return await self._confirmation_handler().start_confirmation(
                event,
                bound_workspace,
                review_action,
            )

        if review_action.action == ChatReviewCallbackData.ACCEPT_SUGGESTION_ACTION:
            return await self._confirmation_handler().accept_suggestion(
                event,
                bound_workspace,
                review_action,
            )

        if review_action.action == ChatReviewCallbackData.TRANSFER_ACTION:
            return await self._transfer_handler().start_transfer(
                event,
                bound_workspace,
                review_action,
            )

        if review_action.action in {
            ChatReviewCallbackData.DUPLICATE_ACTION,
            ChatReviewCallbackData.IGNORE_ACTION,
        }:
            return await self.start_action_confirmation(
                event,
                bound_workspace,
                review_action,
            )

        try:
            result = await ChatReviewActionService(self.session).apply_action(
                context=bound_workspace.context,
                selection=review_action,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        return await self._queue_handler().show_next_item_after_success(
            event,
            bound_workspace,
            result.action_label,
            result.continuation_anchor,
        )

    async def start_action_confirmation(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        review_action: ChatReviewActionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        try:
            confirmation = await ChatReviewActionService(
                self.session,
            ).start_action_confirmation(
                context=bound_workspace.context,
                selection=review_action,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramReviewPresenter.show_action_confirmation(
            event.conversation,
            confirmation,
        )

    async def confirm_action(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        action_confirmation: ChatReviewActionConfirmationSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        try:
            result = await ChatReviewActionService(self.session).confirm_action(
                context=bound_workspace.context,
                selection=action_confirmation,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        return await self._queue_handler().show_next_item_after_success(
            event,
            bound_workspace,
            result.action_label,
            result.continuation_anchor,
        )
