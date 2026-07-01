from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.actions.review import (
    ChatReviewRulePatternSelection,
    ChatReviewRuleSuggestionCallbackData,
    ChatReviewRuleSuggestionSelection,
)
from app.features.chat_integrations.errors import ChatReviewActionError
from app.features.chat_integrations.handlers.review_queue import ChatReviewQueueHandler
from app.features.chat_integrations.presentation.review import TelegramReviewPresenter
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.review.rules import ChatReviewRuleSuggestionService
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


class ChatReviewRuleSuggestionHandler:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None,
    ) -> None:
        self.session = session
        self.settings = settings

    def _queue_handler(self) -> ChatReviewQueueHandler:
        return ChatReviewQueueHandler(self.session, self.settings)

    async def apply_rule_suggestion_action(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatReviewRuleSuggestionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        if selection.action == ChatReviewRuleSuggestionCallbackData.CHOOSE_PATTERN_ACTION:
            return await self.start_rule_pattern_selection(
                event,
                bound_workspace,
                selection,
            )

        if selection.action == ChatReviewRuleSuggestionCallbackData.ENTER_PATTERN_ACTION:
            return await self.start_rule_pattern_input(
                event,
                bound_workspace,
                selection,
            )

        try:
            if selection.action == ChatReviewRuleSuggestionCallbackData.SAVE_ACTION:
                result = await ChatReviewRuleSuggestionService(self.session).save_suggestion(
                    context=bound_workspace.context,
                    selection=selection,
                )
            else:
                result = await ChatReviewRuleSuggestionService(self.session).skip_suggestion(
                    context=bound_workspace.context,
                    selection=selection,
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

    async def start_rule_pattern_selection(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatReviewRuleSuggestionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        try:
            pattern_selection = await ChatReviewRuleSuggestionService(
                self.session,
            ).start_pattern_selection(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramReviewPresenter.show_rule_pattern_menu(
            event.conversation,
            pattern_selection,
        )

    async def start_rule_pattern_input(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatReviewRuleSuggestionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        try:
            pattern_input = await ChatReviewRuleSuggestionService(
                self.session,
            ).start_manual_pattern_input(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )

        return TelegramReviewPresenter.show_rule_pattern_input(
            event.conversation,
            pattern_input,
        )

    async def answer_rule_pattern_message(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        try:
            result = await ChatReviewRuleSuggestionService(self.session).save_manual_pattern(
                context=bound_workspace.context,
                text=event.text,
            )
        except ChatReviewActionError as exc:
            return TelegramReviewPresenter.show_action_error(
                event.conversation,
                str(exc),
            )
        if result is None:
            return None

        return await self._queue_handler().show_next_item_after_success(
            event,
            bound_workspace,
            result.action_label,
            result.continuation_anchor,
        )

    async def save_rule_pattern(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatReviewRulePatternSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        try:
            result = await ChatReviewRuleSuggestionService(self.session).save_pattern_selection(
                context=bound_workspace.context,
                selection=selection,
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
