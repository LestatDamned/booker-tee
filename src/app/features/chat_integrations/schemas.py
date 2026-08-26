from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, BinaryIO


class ChatProviderCode(StrEnum):
    FAKE = "fake"
    MATRIX = "matrix"
    TELEGRAM = "telegram"


class ChatConversationType(StrEnum):
    CHANNEL = "channel"
    GROUP = "group"
    PRIVATE = "private"
    UNKNOWN = "unknown"


class InboundChatEventType(StrEnum):
    CALLBACK_QUERY = "callback_query"
    DOCUMENT = "document"
    MESSAGE = "message"
    UNKNOWN = "unknown"


class OutboundChatDeliveryMode(StrEnum):
    SEND_NEW = "send_new"
    EDIT_SOURCE_MESSAGE = "edit_source_message"


@dataclass(frozen=True)
class ChatUser:
    provider: ChatProviderCode
    external_user_id: str
    display_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    is_bot: bool = False


@dataclass(frozen=True)
class ChatConversation:
    provider: ChatProviderCode
    external_chat_id: str
    conversation_type: ChatConversationType
    title: str | None = None


@dataclass(frozen=True)
class ChatDocument:
    file_id: str
    file_unique_id: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None


@dataclass(frozen=True)
class ChatDownloadedFile:
    filename: str
    content_type: str | None
    file: BinaryIO
    file_size: int


@dataclass(frozen=True)
class InboundChatEvent:
    provider: ChatProviderCode
    event_id: str
    event_type: InboundChatEventType
    conversation: ChatConversation | None
    actor: ChatUser | None
    text: str | None = None
    callback_data: str | None = None
    callback_query_id: str | None = None
    source_message_id: str | None = None
    document: ChatDocument | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OutboundChatButton:
    text: str
    callback_data: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class OutboundChatMessage:
    conversation: ChatConversation
    text: str
    buttons: tuple[tuple[OutboundChatButton, ...], ...] = ()
    delivery_mode: OutboundChatDeliveryMode = OutboundChatDeliveryMode.SEND_NEW
    callback_notification: str | None = None
    target_message_id: str | None = None
