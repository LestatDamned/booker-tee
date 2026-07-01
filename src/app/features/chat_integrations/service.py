from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.application import ChatReviewUrlBuilder
from app.features.chat_integrations.errors import ChatWorkspaceResolutionError
from app.features.chat_integrations.handlers.factory import ChatEventHandlers
from app.features.chat_integrations.presenters import TelegramMainMenuPresenter
from app.features.chat_integrations.providers.base import ChatDocumentDownloader, ChatProvider
from app.features.chat_integrations.routing.chain import ChatBoundCallbackChain
from app.features.chat_integrations.routing.message_chain import ChatBoundMessageChain
from app.features.chat_integrations.schemas import (
    ChatConversationType,
    InboundChatEvent,
    InboundChatEventType,
    OutboundChatMessage,
)
from app.features.chat_integrations.use_cases.dashboard import (
    ChatPrivateStatus,
    ChatPrivateStatusReader,
)
from app.features.chat_integrations.use_cases.workspace import (
    BoundChatWorkspace,
    WorkspaceChatResolver,
)


class ChatEventService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        settings: Settings | None = None,
        document_downloader: ChatDocumentDownloader | None = None,
        chat_provider: ChatProvider | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.document_downloader = document_downloader
        self.chat_provider = chat_provider

    async def receive_inbound_event(self, event: InboundChatEvent) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        bound_workspace = await self._resolve_bound_workspace(event)
        if bound_workspace is not None:
            return await self._answer_bound_event(event, bound_workspace)

        if self._is_start_message(event):
            return TelegramMainMenuPresenter.show_welcome_menu(event.conversation)

        if event.event_type == InboundChatEventType.CALLBACK_QUERY:
            return self._answer_unbound_callback_query(event)

        return TelegramMainMenuPresenter.show_safe_fallback(event.conversation)

    @staticmethod
    def _is_start_message(event: InboundChatEvent) -> bool:
        return event.event_type == InboundChatEventType.MESSAGE and event.text == "/start"

    def _handlers(self) -> ChatEventHandlers:
        assert self.session is not None
        return ChatEventHandlers(
            self.session,
            self.settings,
            self.document_downloader,
            self.chat_provider,
        )

    def _callback_chain(self, handlers: ChatEventHandlers) -> ChatBoundCallbackChain:
        return ChatBoundCallbackChain.build(
            handlers,
            self._read_private_status,
            self._imports_url,
        )

    @staticmethod
    def _message_chain(handlers: ChatEventHandlers) -> ChatBoundMessageChain:
        return ChatBoundMessageChain.build(handlers)

    def _imports_url(self) -> str | None:
        return ChatReviewUrlBuilder.build_imports_url(self.settings)

    async def _read_private_status(
        self,
        bound_workspace: BoundChatWorkspace,
    ) -> ChatPrivateStatus:
        assert self.session is not None
        return await ChatPrivateStatusReader(self.session).read_status(bound_workspace.context)

    def _show_bound_menu(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        status: ChatPrivateStatus,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        return TelegramMainMenuPresenter.show_bound_menu(
            event.conversation,
            bound_workspace.context,
            status,
            self._imports_url(),
        )

    async def _resolve_bound_workspace(self, event: InboundChatEvent) -> BoundChatWorkspace | None:
        if self.session is None or event.actor is None:
            return None
        try:
            return await WorkspaceChatResolver(self.session).require_bound_workspace(event)
        except ChatWorkspaceResolutionError:
            return None

    async def _answer_bound_event(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None or self.session is None:
            return None

        if event.conversation.conversation_type != ChatConversationType.PRIVATE:
            return TelegramMainMenuPresenter.show_group_private_actions_notice(event.conversation)

        handlers = self._handlers()

        if event.event_type == InboundChatEventType.DOCUMENT:
            return await handlers.upload().start_document_upload(event, bound_workspace)

        if event.event_type == InboundChatEventType.CALLBACK_QUERY:
            return await self._callback_chain(handlers).answer_if_matches(event, bound_workspace)

        if event.event_type == InboundChatEventType.MESSAGE and not self._is_start_message(event):
            response = await self._message_chain(handlers).answer_if_matches(
                event,
                bound_workspace,
            )
            if response is not None:
                return response

        status = await self._read_private_status(bound_workspace)
        return self._show_bound_menu(event, bound_workspace, status)

    @staticmethod
    def _answer_unbound_callback_query(event: InboundChatEvent) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        match event.callback_data:
            case "main:menu":
                return TelegramMainMenuPresenter.show_welcome_menu(event.conversation)
            case "help:show":
                return TelegramMainMenuPresenter.show_help(event.conversation)
            case "link:start":
                return TelegramMainMenuPresenter.show_unlinked_account_notice(
                    event.conversation,
                    event.actor,
                )
            case _:
                return TelegramMainMenuPresenter.show_unlinked_account_notice(
                    event.conversation,
                    event.actor,
                )
