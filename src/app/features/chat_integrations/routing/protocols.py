from collections.abc import Awaitable, Callable
from typing import Protocol

from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.dashboard import ChatPrivateStatus
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace

type ReadPrivateStatus = Callable[[BoundChatWorkspace], Awaitable[ChatPrivateStatus]]
type BuildImportsUrl = Callable[[], str | None]


class BoundCallbackHandler(Protocol):
    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None: ...


class BoundMessageHandler(Protocol):
    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None: ...
