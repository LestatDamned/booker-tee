from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.actions.review import (
    ChatReviewActionSelection,
    ChatReviewCategoryPageSelection,
    ChatReviewCategorySelection,
    ChatReviewPropertySelection,
)
from app.features.chat_integrations.errors import ChatReviewActionError
from app.features.chat_integrations.handlers.review_queue import ChatReviewQueueHandler
from app.features.chat_integrations.presentation.review import TelegramReviewPresenter
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.review.confirmation import (
    ChatReviewConfirmationService,
)
from app.features.chat_integrations.use_cases.review.dto import ChatReviewCategoryActionResult
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


class ChatReviewConfirmationHandler:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None,
    ) -> None:
        self.session = session
        self.settings = settings

    def _queue_handler(self) -> ChatReviewQueueHandler:
        return ChatReviewQueueHandler(self.session, self.settings)

    async def start_confirmation(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        review_action: ChatReviewActionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.settings is None:
            return None

        try:
            selection = await ChatReviewConfirmationService(
                self.session,
                self.settings,
            ).start_category_selection(
                context=bound_workspace.context,
                action_token=review_action.action_token,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramReviewPresenter.show_category_menu(
            event.conversation,
            selection,
        )

    async def change_category_page(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        category_page_selection: ChatReviewCategoryPageSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.settings is None:
            return None

        try:
            selection = await ChatReviewConfirmationService(
                self.session,
                self.settings,
            ).change_category_page(
                context=bound_workspace.context,
                selection=category_page_selection,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramReviewPresenter.show_category_menu(
            event.conversation,
            selection,
        )

    async def accept_suggestion(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        review_action: ChatReviewActionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.settings is None:
            return None

        try:
            category_result = await ChatReviewConfirmationService(
                self.session,
                self.settings,
            ).confirm_with_suggestion(
                context=bound_workspace.context,
                action_token=review_action.action_token,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        return await self.show_category_result(event, bound_workspace, category_result)

    async def complete_confirmation(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        category_selection: ChatReviewCategorySelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.settings is None:
            return None

        try:
            category_result = await ChatReviewConfirmationService(
                self.session,
                self.settings,
            ).confirm_with_category(
                context=bound_workspace.context,
                selection=category_selection,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        return await self.show_category_result(event, bound_workspace, category_result)

    async def show_category_result(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        category_result: ChatReviewCategoryActionResult,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        if category_result.property_selection is not None:
            return TelegramReviewPresenter.show_property_menu(
                event.conversation,
                category_result.property_selection,
            )

        if category_result.action_result is None:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                "Stored review action is invalid.",
            )

        if category_result.rule_suggestion is not None:
            return TelegramReviewPresenter.show_rule_suggestion(
                event.conversation,
                category_result.rule_suggestion,
            )

        return await self._queue_handler().show_next_item_after_success(
            event,
            bound_workspace,
            category_result.action_result.action_label,
            category_result.action_result.continuation_anchor,
        )

    async def complete_property_confirmation(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        property_selection: ChatReviewPropertySelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.settings is None:
            return None

        try:
            category_result = await ChatReviewConfirmationService(
                self.session,
                self.settings,
            ).confirm_with_property(
                context=bound_workspace.context,
                selection=property_selection,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        return await self.show_category_result(event, bound_workspace, category_result)
