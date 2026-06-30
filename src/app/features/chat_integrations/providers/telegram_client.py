from dataclasses import dataclass
from typing import Any

import httpx

from app.features.chat_integrations.providers.telegram import (
    TELEGRAM_ALLOWED_UPDATES,
    TelegramCallbackDataPolicy,
)
from app.features.chat_integrations.schemas import (
    ChatConversation,
    ChatDocument,
    ChatDownloadedFile,
    InboundChatEvent,
    OutboundChatButton,
    OutboundChatDeliveryMode,
    OutboundChatMessage,
)

TELEGRAM_API_BASE_URL = "https://api.telegram.org"


class TelegramBotClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class TelegramBotClient:
    bot_token: str
    http_client: httpx.AsyncClient
    api_base_url: str = TELEGRAM_API_BASE_URL

    async def get_updates(
        self,
        *,
        offset: int | None,
        timeout_seconds: int,
        allowed_updates: tuple[str, ...] = TELEGRAM_ALLOWED_UPDATES,
    ) -> list[dict[str, object]]:
        payload: dict[str, object] = {
            "timeout": timeout_seconds,
            "allowed_updates": list(allowed_updates),
        }
        if offset is not None:
            payload["offset"] = offset

        response = await self._post_json("getUpdates", payload)
        result = response.get("result")
        if not isinstance(result, list):
            raise TelegramBotClientError("Telegram getUpdates response result must be a list.")

        return [item for item in result if isinstance(item, dict)]

    async def send_message(self, message: OutboundChatMessage) -> None:
        await self._post_json("sendMessage", TelegramSendMessagePayloadBuilder.build(message))

    async def edit_message_text(self, *, message: OutboundChatMessage, message_id: str) -> None:
        await self._post_json(
            "editMessageText",
            TelegramEditMessageTextPayloadBuilder.build(message=message, message_id=message_id),
        )

    async def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str | None = None,
    ) -> None:
        payload: dict[str, object] = {"callback_query_id": callback_query_id}
        if text is not None:
            payload["text"] = text
        await self._post_json("answerCallbackQuery", payload)

    async def set_webhook(
        self,
        *,
        url: str,
        secret_token: str,
        allowed_updates: tuple[str, ...] = TELEGRAM_ALLOWED_UPDATES,
        drop_pending_updates: bool = False,
    ) -> None:
        await self._post_json(
            "setWebhook",
            {
                "url": url,
                "secret_token": secret_token,
                "allowed_updates": list(allowed_updates),
                "drop_pending_updates": drop_pending_updates,
            },
        )

    async def delete_webhook(self, *, drop_pending_updates: bool = False) -> None:
        await self._post_json(
            "deleteWebhook",
            {"drop_pending_updates": drop_pending_updates},
        )

    async def download_document(self, document: ChatDocument) -> ChatDownloadedFile:
        file_path = await self.get_file_path(document.file_id)
        response = await self.http_client.get(self._file_url(file_path))
        response.raise_for_status()
        return ChatDownloadedFile(
            filename=document.file_name or "statement",
            content_type=document.mime_type,
            file_bytes=response.content,
        )

    async def get_file_path(self, file_id: str) -> str:
        response = await self._post_json("getFile", {"file_id": file_id})
        result = response.get("result")
        if not isinstance(result, dict):
            raise TelegramBotClientError("Telegram getFile response result must be an object.")

        file_path = result.get("file_path")
        if not isinstance(file_path, str) or not file_path:
            raise TelegramBotClientError("Telegram getFile response did not include file_path.")
        return file_path

    async def _post_json(self, method: str, payload: dict[str, object]) -> dict[str, Any]:
        response = await self.http_client.post(self._method_url(method), json=payload)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or data.get("ok") is not True:
            description = data.get("description") if isinstance(data, dict) else None
            raise TelegramBotClientError(str(description or f"Telegram method failed: {method}"))
        return data

    def _method_url(self, method: str) -> str:
        return f"{self.api_base_url}/bot{self.bot_token}/{method}"

    def _file_url(self, file_path: str) -> str:
        return f"{self.api_base_url}/file/bot{self.bot_token}/{file_path}"


class TelegramSendMessagePayloadBuilder:
    @staticmethod
    def build(message: OutboundChatMessage) -> dict[str, object]:
        payload: dict[str, object] = {
            "chat_id": TelegramChatIdReader.read_from_conversation(message.conversation),
            "text": message.text,
        }

        reply_markup = TelegramInlineKeyboardBuilder.build_reply_markup(message.buttons)
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        return payload


class TelegramEditMessageTextPayloadBuilder:
    @staticmethod
    def build(*, message: OutboundChatMessage, message_id: str) -> dict[str, object]:
        payload = TelegramMessageTextPayloadBuilder.build(message)
        payload["message_id"] = TelegramMessageIdReader.read(message_id)
        return payload


class TelegramMessageTextPayloadBuilder:
    @staticmethod
    def build(message: OutboundChatMessage) -> dict[str, object]:
        payload: dict[str, object] = {
            "chat_id": TelegramChatIdReader.read_from_conversation(message.conversation),
            "text": message.text,
        }

        reply_markup = TelegramInlineKeyboardBuilder.build_reply_markup(message.buttons)
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        return payload


class TelegramOutboundMessageSender:
    @staticmethod
    async def send_response(
        *,
        client: TelegramBotClient,
        event: InboundChatEvent,
        response: OutboundChatMessage | None,
    ) -> None:
        await TelegramOutboundMessageSender._answer_callback_query(client, event, response)
        if response is None:
            return

        if (
            response.delivery_mode == OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE
            and event.source_message_id is not None
        ):
            try:
                await client.edit_message_text(
                    message=response,
                    message_id=event.source_message_id,
                )
                return
            except TelegramBotClientError as exc:
                if TelegramMessageEditFallbackPolicy.is_noop_edit_error(exc):
                    return

        await client.send_message(response)

    @staticmethod
    async def _answer_callback_query(
        client: TelegramBotClient,
        event: InboundChatEvent,
        response: OutboundChatMessage | None,
    ) -> None:
        if event.callback_query_id is None:
            return

        await client.answer_callback_query(
            callback_query_id=event.callback_query_id,
            text=response.callback_notification if response is not None else None,
        )


class TelegramMessageEditFallbackPolicy:
    @staticmethod
    def is_noop_edit_error(exc: TelegramBotClientError) -> bool:
        return "message is not modified" in str(exc).casefold()


class TelegramInlineKeyboardBuilder:
    @staticmethod
    def build_reply_markup(
        buttons: tuple[tuple[OutboundChatButton, ...], ...],
    ) -> dict[str, object] | None:
        if not buttons:
            return None

        return {
            "inline_keyboard": [
                [TelegramInlineKeyboardButtonBuilder.build(button) for button in row]
                for row in buttons
            ],
        }


class TelegramInlineKeyboardButtonBuilder:
    @staticmethod
    def build(button: OutboundChatButton) -> dict[str, str]:
        payload = {"text": button.text}
        if button.callback_data is not None:
            payload["callback_data"] = TelegramCallbackDataPolicy.ensure_callback_data(
                button.callback_data
            )
        if button.url is not None:
            payload["url"] = button.url
        return payload


class TelegramChatIdReader:
    @staticmethod
    def read_from_conversation(conversation: ChatConversation) -> int | str:
        try:
            return int(conversation.external_chat_id)
        except ValueError:
            return conversation.external_chat_id


class TelegramMessageIdReader:
    @staticmethod
    def read(message_id: str) -> int | str:
        try:
            return int(message_id)
        except ValueError:
            return message_id
