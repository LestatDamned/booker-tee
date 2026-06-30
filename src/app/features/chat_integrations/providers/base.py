from typing import Protocol

from app.features.chat_integrations.schemas import (
    ChatDocument,
    ChatDownloadedFile,
    InboundChatEvent,
    OutboundChatMessage,
)


class ChatProvider(Protocol):
    async def send_message(self, message: OutboundChatMessage) -> None: ...


class ChatDocumentDownloader(Protocol):
    async def download_document(self, document: ChatDocument) -> ChatDownloadedFile: ...


class ChatUpdateNormalizer(Protocol):
    def normalize_update(self, payload: dict[str, object]) -> InboundChatEvent: ...
