from collections.abc import Mapping
from typing import Any, cast

from app.features.chat_integrations.schemas import (
    ChatConversation,
    ChatConversationType,
    ChatDocument,
    ChatProviderCode,
    ChatUser,
    InboundChatEvent,
    InboundChatEventType,
)

TELEGRAM_MAX_CALLBACK_DATA_BYTES = 64
TELEGRAM_ALLOWED_UPDATES = ("message", "callback_query")

TelegramPayload = Mapping[str, Any]


class TelegramUpdateNormalizationError(ValueError):
    pass


class TelegramCallbackDataPolicy:
    @staticmethod
    def ensure_callback_data(callback_data: str) -> str:
        size = len(callback_data.encode("utf-8"))
        if size < 1 or size > TELEGRAM_MAX_CALLBACK_DATA_BYTES:
            raise TelegramUpdateNormalizationError(
                "Telegram callback_data must be 1-64 bytes after UTF-8 encoding."
            )
        return callback_data


class TelegramUpdateNormalizer:
    @staticmethod
    def normalize_update(payload: dict[str, object]) -> InboundChatEvent:
        if TelegramCallbackQueryReader.has_callback_query(payload):
            return TelegramCallbackQueryReader.read_event(payload)
        if TelegramMessageReader.has_message(payload):
            return TelegramMessageReader.read_event(payload)
        return TelegramUnknownUpdateReader.read_event(payload)


class TelegramMessageReader:
    @staticmethod
    def has_message(payload: TelegramPayload) -> bool:
        return "message" in payload

    @staticmethod
    def read_event(payload: TelegramPayload) -> InboundChatEvent:
        message = TelegramPayloadReader.require_object(payload, "message")
        document = TelegramDocumentReader.read_from_message(message)
        event_type = InboundChatEventType.DOCUMENT if document else InboundChatEventType.MESSAGE

        return InboundChatEvent(
            provider=ChatProviderCode.TELEGRAM,
            event_id=TelegramPayloadReader.read_update_id(payload),
            event_type=event_type,
            conversation=TelegramConversationReader.read_from_message(message),
            actor=TelegramUserReader.read_from_payload(message.get("from")),
            text=TelegramPayloadReader.read_string(message.get("text")),
            source_message_id=TelegramPayloadReader.read_message_id(message),
            document=document,
            raw_payload=dict(payload),
        )


class TelegramCallbackQueryReader:
    @staticmethod
    def has_callback_query(payload: TelegramPayload) -> bool:
        return "callback_query" in payload

    @staticmethod
    def read_event(payload: TelegramPayload) -> InboundChatEvent:
        callback_query = TelegramPayloadReader.require_object(payload, "callback_query")
        message = callback_query.get("message")
        callback_id = TelegramPayloadReader.read_string(callback_query.get("id"))
        update_id = TelegramPayloadReader.read_update_id(payload)
        event_id = f"{update_id}:callback:{callback_id}" if callback_id else update_id

        return InboundChatEvent(
            provider=ChatProviderCode.TELEGRAM,
            event_id=event_id,
            event_type=InboundChatEventType.CALLBACK_QUERY,
            conversation=TelegramConversationReader.read_from_message(message),
            actor=TelegramUserReader.read_from_payload(callback_query.get("from")),
            text=TelegramMessageTextReader.read_from_message(message),
            callback_data=TelegramPayloadReader.read_string(callback_query.get("data")),
            callback_query_id=callback_id,
            source_message_id=TelegramPayloadReader.read_message_id(message),
            raw_payload=dict(payload),
        )


class TelegramUnknownUpdateReader:
    @staticmethod
    def read_event(payload: TelegramPayload) -> InboundChatEvent:
        return InboundChatEvent(
            provider=ChatProviderCode.TELEGRAM,
            event_id=TelegramPayloadReader.read_update_id(payload),
            event_type=InboundChatEventType.UNKNOWN,
            conversation=None,
            actor=None,
            raw_payload=dict(payload),
        )


class TelegramConversationReader:
    @staticmethod
    def read_from_message(message: object) -> ChatConversation | None:
        if not isinstance(message, Mapping):
            return None

        chat = message.get("chat")
        if not isinstance(chat, Mapping):
            return None
        chat_payload = cast(TelegramPayload, chat)

        return ChatConversation(
            provider=ChatProviderCode.TELEGRAM,
            external_chat_id=str(chat.get("id", "")),
            conversation_type=TelegramConversationTypeReader.read_from_chat(chat_payload),
            title=TelegramChatTitleReader.read_from_chat(chat_payload),
        )


class TelegramConversationTypeReader:
    @staticmethod
    def read_from_chat(chat: TelegramPayload) -> ChatConversationType:
        value = chat.get("type")
        if value == "private":
            return ChatConversationType.PRIVATE
        if value in {"group", "supergroup"}:
            return ChatConversationType.GROUP
        if value == "channel":
            return ChatConversationType.CHANNEL
        return ChatConversationType.UNKNOWN


class TelegramChatTitleReader:
    @staticmethod
    def read_from_chat(chat: TelegramPayload) -> str | None:
        title = TelegramPayloadReader.read_string(chat.get("title"))
        if title:
            return title

        first_name = TelegramPayloadReader.read_string(chat.get("first_name"))
        last_name = TelegramPayloadReader.read_string(chat.get("last_name"))
        return TelegramDisplayNameReader.read_from_names(first_name, last_name)


class TelegramUserReader:
    @staticmethod
    def read_from_payload(payload: object) -> ChatUser | None:
        if not isinstance(payload, Mapping):
            return None

        first_name = TelegramPayloadReader.read_string(payload.get("first_name"))
        last_name = TelegramPayloadReader.read_string(payload.get("last_name"))
        return ChatUser(
            provider=ChatProviderCode.TELEGRAM,
            external_user_id=str(payload.get("id", "")),
            display_name=TelegramDisplayNameReader.read_from_names(first_name, last_name),
            username=TelegramPayloadReader.read_string(payload.get("username")),
            language_code=TelegramPayloadReader.read_string(payload.get("language_code")),
            is_bot=payload.get("is_bot") is True,
        )


class TelegramDocumentReader:
    @staticmethod
    def read_from_message(message: TelegramPayload) -> ChatDocument | None:
        document = message.get("document")
        if not isinstance(document, Mapping):
            return None

        file_id = TelegramPayloadReader.read_string(document.get("file_id"))
        if file_id is None:
            return None

        return ChatDocument(
            file_id=file_id,
            file_unique_id=TelegramPayloadReader.read_string(document.get("file_unique_id")),
            file_name=TelegramPayloadReader.read_string(document.get("file_name")),
            mime_type=TelegramPayloadReader.read_string(document.get("mime_type")),
            file_size=TelegramPayloadReader.read_int(document.get("file_size")),
        )


class TelegramMessageTextReader:
    @staticmethod
    def read_from_message(message: object) -> str | None:
        if not isinstance(message, Mapping):
            return None
        return TelegramPayloadReader.read_string(message.get("text"))


class TelegramDisplayNameReader:
    @staticmethod
    def read_from_names(first_name: str | None, last_name: str | None) -> str | None:
        name = " ".join(part for part in (first_name, last_name) if part)
        return name or None


class TelegramPayloadReader:
    @staticmethod
    def require_object(payload: TelegramPayload, key: str) -> TelegramPayload:
        value = payload.get(key)
        if not isinstance(value, Mapping):
            raise TelegramUpdateNormalizationError(
                f"Telegram update is missing object field: {key}."
            )
        return value

    @staticmethod
    def read_update_id(payload: TelegramPayload) -> str:
        update_id = payload.get("update_id")
        if isinstance(update_id, int):
            return str(update_id)
        return "unknown"

    @staticmethod
    def read_string(value: object) -> str | None:
        return value if isinstance(value, str) else None

    @staticmethod
    def read_int(value: object) -> int | None:
        return value if isinstance(value, int) else None

    @staticmethod
    def read_message_id(message: object) -> str | None:
        if not isinstance(message, Mapping):
            return None

        message_id = message.get("message_id")
        if isinstance(message_id, int):
            return str(message_id)
        return None
