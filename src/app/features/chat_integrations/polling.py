import asyncio
from dataclasses import dataclass, field

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.settings import Settings
from app.features.chat_integrations.providers.telegram import TelegramUpdateNormalizer
from app.features.chat_integrations.providers.telegram_client import (
    TelegramBotClient,
    TelegramOutboundMessageSender,
    create_telegram_http_client,
)
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.service import ChatEventService


class TelegramPollingConfigurationError(RuntimeError):
    pass


@dataclass
class TelegramPollingWorker:
    client: TelegramBotClient
    timeout_seconds: int
    settings: Settings | None = None
    session_factory: async_sessionmaker[AsyncSession] | None = None
    seen_update_ids: set[int] = field(default_factory=set)
    next_offset: int | None = None

    async def run_once(self) -> int:
        updates = await self.client.get_updates(
            offset=self.next_offset,
            timeout_seconds=self.timeout_seconds,
        )
        handled_count = 0

        for update in updates:
            update_id = TelegramUpdateIdReader.read_from_update(update)
            if update_id is not None:
                self.next_offset = update_id + 1
            if update_id is not None and update_id in self.seen_update_ids:
                continue
            if update_id is not None:
                self.seen_update_ids.add(update_id)

            event = TelegramUpdateNormalizer.normalize_update(update)
            response = await self._answer_event(event)
            await TelegramOutboundMessageSender.send_response(
                client=self.client,
                event=event,
                response=response,
            )
            handled_count += 1

        return handled_count

    async def _answer_event(self, event: InboundChatEvent) -> OutboundChatMessage | None:
        if self.session_factory is None:
            return await ChatEventService().receive_inbound_event(event)

        async with self.session_factory() as session:
            return await ChatEventService(
                session,
                self.settings,
                self.client,
                self.client,
            ).receive_inbound_event(event)

    async def run_forever(self) -> None:
        while True:
            await self.run_once()


class TelegramUpdateIdReader:
    @staticmethod
    def read_from_update(update: dict[str, object]) -> int | None:
        update_id = update.get("update_id")
        return update_id if isinstance(update_id, int) else None


class TelegramPollingWorkerFactory:
    @staticmethod
    def create_from_settings(
        settings: Settings,
        http_client: httpx.AsyncClient,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> TelegramPollingWorker:
        if not settings.chat_integrations_enabled:
            raise TelegramPollingConfigurationError("Chat integrations are disabled.")
        if settings.telegram_mode != "polling":
            raise TelegramPollingConfigurationError(
                "Telegram polling worker requires polling mode."
            )
        if settings.telegram_bot_token is None:
            raise TelegramPollingConfigurationError("BOOKER_TEE_TELEGRAM_BOT_TOKEN is required.")

        return TelegramPollingWorker(
            client=TelegramBotClient(
                bot_token=settings.telegram_bot_token,
                http_client=http_client,
                download_max_bytes=settings.statement_upload_max_bytes,
            ),
            timeout_seconds=settings.telegram_polling_timeout_seconds,
            settings=settings,
            session_factory=session_factory,
        )


async def run_telegram_polling_from_settings() -> None:
    from app.db.session import session_factory

    settings = get_settings()
    async with create_telegram_http_client(settings) as client:
        worker = TelegramPollingWorkerFactory.create_from_settings(
            settings,
            client,
            session_factory,
        )
        await worker.run_forever()


def main() -> None:
    asyncio.run(run_telegram_polling_from_settings())


if __name__ == "__main__":
    main()
