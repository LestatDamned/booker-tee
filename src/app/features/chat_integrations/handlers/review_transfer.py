from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.actions.review import (
    ChatReviewActionSelection,
    ChatReviewTransferAccountSelection,
    ChatReviewTransferConfirmationSelection,
    ChatReviewTransferPairSelection,
)
from app.features.chat_integrations.errors import ChatReviewActionError
from app.features.chat_integrations.handlers.review_queue import ChatReviewQueueHandler
from app.features.chat_integrations.presentation.review import TelegramReviewPresenter
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.review.transfers import ChatReviewTransferService
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


class ChatReviewTransferHandler:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None,
    ) -> None:
        self.session = session
        self.settings = settings

    def _queue_handler(self) -> ChatReviewQueueHandler:
        return ChatReviewQueueHandler(self.session, self.settings)

    async def start_transfer(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        review_action: ChatReviewActionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.settings is None:
            return None

        try:
            selection = await ChatReviewTransferService(
                self.session,
                self.settings,
            ).start_transfer_selection(
                context=bound_workspace.context,
                action_token=review_action.action_token,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramReviewPresenter.show_transfer_account_menu(
            event.conversation,
            selection,
        )

    async def complete_transfer(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        transfer_account_selection: ChatReviewTransferAccountSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.settings is None:
            return None

        try:
            confirmation = await ChatReviewTransferService(
                self.session,
                self.settings,
            ).start_transfer_confirmation_with_account(
                context=bound_workspace.context,
                selection=transfer_account_selection,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramReviewPresenter.show_transfer_confirmation(
            event.conversation,
            confirmation,
        )

    async def complete_transfer_pair(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        transfer_pair_selection: ChatReviewTransferPairSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.settings is None:
            return None

        try:
            confirmation = await ChatReviewTransferService(
                self.session,
                self.settings,
            ).start_transfer_confirmation_with_pair(
                context=bound_workspace.context,
                selection=transfer_pair_selection,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramReviewPresenter.show_transfer_confirmation(
            event.conversation,
            confirmation,
        )

    async def confirm_transfer(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        transfer_confirmation: ChatReviewTransferConfirmationSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.settings is None:
            return None

        try:
            result = await ChatReviewTransferService(
                self.session,
                self.settings,
            ).confirm_transfer(
                context=bound_workspace.context,
                selection=transfer_confirmation,
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
