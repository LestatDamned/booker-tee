from dataclasses import dataclass

from app.features.chat_integrations.handlers.factory import ChatEventHandlers
from app.features.chat_integrations.routing.protocols import BoundMessageHandler
from app.features.chat_integrations.schemas import (
    InboundChatEvent,
    InboundChatEventType,
    OutboundChatMessage,
)
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


@dataclass(frozen=True)
class ChatBoundMessageChain:
    handlers: tuple[BoundMessageHandler, ...]

    @classmethod
    def build(cls, handlers: ChatEventHandlers) -> "ChatBoundMessageChain":
        return cls(
            handlers=(
                ChatManualTextMessageHandler(handlers),
                ChatReviewRulePatternMessageHandler(handlers),
            )
        )

    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.event_type != InboundChatEventType.MESSAGE:
            return None

        for handler in self.handlers:
            response = await handler.answer_if_matches(event, bound_workspace)
            if response is not None:
                return response

        return None


@dataclass(frozen=True)
class ChatManualTextMessageHandler:
    handlers: ChatEventHandlers

    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        return await self.handlers.manual().answer_text_input(event, bound_workspace)


@dataclass(frozen=True)
class ChatReviewRulePatternMessageHandler:
    handlers: ChatEventHandlers

    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        return await self.handlers.review_rule_suggestion().answer_rule_pattern_message(
            event,
            bound_workspace,
        )
