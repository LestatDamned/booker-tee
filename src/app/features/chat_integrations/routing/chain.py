from dataclasses import dataclass

from app.features.chat_integrations.handlers.factory import ChatEventHandlers
from app.features.chat_integrations.routing.dashboard import ChatDashboardCallbackHandler
from app.features.chat_integrations.routing.manual import ChatManualCallbackHandler
from app.features.chat_integrations.routing.menu import ChatBoundMenuCallbackHandler
from app.features.chat_integrations.routing.protocols import (
    BoundCallbackHandler,
    BuildImportsUrl,
    ReadPrivateStatus,
)
from app.features.chat_integrations.routing.review_actions import (
    ChatReviewActionCallbackHandler,
)
from app.features.chat_integrations.routing.review_confirmation import (
    ChatReviewConfirmationCallbackHandler,
)
from app.features.chat_integrations.routing.review_queue import ChatReviewQueueCallbackHandler
from app.features.chat_integrations.routing.review_rules import (
    ChatReviewRuleSuggestionCallbackHandler,
)
from app.features.chat_integrations.routing.review_transfer import (
    ChatReviewTransferCallbackHandler,
)
from app.features.chat_integrations.routing.upload import ChatUploadCallbackHandler
from app.features.chat_integrations.routing.workspace import ChatWorkspaceCallbackHandler
from app.features.chat_integrations.schemas import (
    InboundChatEvent,
    InboundChatEventType,
    OutboundChatMessage,
)
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace


@dataclass(frozen=True)
class ChatBoundCallbackChain:
    handlers: tuple[BoundCallbackHandler, ...]

    @classmethod
    def build(
        cls,
        handlers: ChatEventHandlers,
        read_private_status: ReadPrivateStatus,
        build_imports_url: BuildImportsUrl,
    ) -> "ChatBoundCallbackChain":
        return cls(
            handlers=(
                ChatUploadCallbackHandler(handlers),
                ChatReviewQueueCallbackHandler(handlers),
                ChatManualCallbackHandler(handlers),
                ChatReviewRuleSuggestionCallbackHandler(handlers),
                ChatReviewTransferCallbackHandler(handlers),
                ChatReviewConfirmationCallbackHandler(handlers),
                ChatReviewActionCallbackHandler(handlers),
                ChatWorkspaceCallbackHandler(handlers),
                ChatDashboardCallbackHandler(handlers),
                ChatBoundMenuCallbackHandler(
                    handlers,
                    read_private_status,
                    build_imports_url,
                ),
            )
        )

    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.event_type != InboundChatEventType.CALLBACK_QUERY:
            return None

        for handler in self.handlers:
            response = await handler.answer_if_matches(event, bound_workspace)
            if response is not None:
                return response

        return None
