from dataclasses import dataclass

from app.features.chat_integrations.actions.review import (
    ChatReviewRulePatternCallbackData,
    ChatReviewRuleSuggestionCallbackData,
)
from app.features.chat_integrations.handlers.factory import ChatEventHandlers
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


@dataclass(frozen=True)
class ChatReviewRuleSuggestionCallbackHandler:
    handlers: ChatEventHandlers

    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        pattern_selection = ChatReviewRulePatternCallbackData.parse_pattern_selection(
            event.callback_data
        )
        if pattern_selection is not None:
            return await self.handlers.review_rule_suggestion().save_rule_pattern(
                event,
                bound_workspace,
                pattern_selection,
            )

        suggestion_action = ChatReviewRuleSuggestionCallbackData.parse_action(event.callback_data)
        if suggestion_action is None:
            return None

        return await self.handlers.review_rule_suggestion().apply_rule_suggestion_action(
            event,
            bound_workspace,
            suggestion_action,
        )
