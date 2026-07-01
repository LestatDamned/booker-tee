from dataclasses import dataclass

from app.features.chat_integrations.handlers.factory import ChatEventHandlers
from app.features.chat_integrations.presentation.dashboard import TelegramDashboardPresenter
from app.features.chat_integrations.presentation.manual import TelegramManualPresenter
from app.features.chat_integrations.presentation.upload import TelegramUploadPresenter
from app.features.chat_integrations.presenters import TelegramMainMenuPresenter
from app.features.chat_integrations.routing.protocols import (
    BuildImportsUrl,
    ReadPrivateStatus,
)
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace
from app.features.ledger.models import OperationType


@dataclass(frozen=True)
class ChatBoundMenuCallbackHandler:
    handlers: ChatEventHandlers
    read_private_status: ReadPrivateStatus
    build_imports_url: BuildImportsUrl

    async def answer_if_matches(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None

        match event.callback_data:
            case "main:menu":
                status = await self.read_private_status(bound_workspace)
                return TelegramMainMenuPresenter.show_bound_menu(
                    event.conversation,
                    bound_workspace.context,
                    status,
                    self.build_imports_url(),
                )
            case "status:show":
                status = await self.read_private_status(bound_workspace)
                return TelegramDashboardPresenter.show_private_status(
                    event.conversation,
                    bound_workspace.context,
                    status,
                    self.build_imports_url(),
                )
            case "upload:start":
                return TelegramUploadPresenter.show_instructions(event.conversation)
            case "manual:start":
                return TelegramManualPresenter.show_type_menu(event.conversation)
            case "manual:expense":
                return await self.handlers.manual().start_income_expense(
                    event,
                    bound_workspace,
                    OperationType.EXPENSE,
                )
            case "manual:income":
                return await self.handlers.manual().start_income_expense(
                    event,
                    bound_workspace,
                    OperationType.INCOME,
                )
            case "manual:transfer":
                return await self.handlers.manual().start_transfer(event, bound_workspace)
            case "help:show":
                return TelegramMainMenuPresenter.show_help(event.conversation)
            case _:
                status = await self.read_private_status(bound_workspace)
                return TelegramMainMenuPresenter.show_bound_menu(
                    event.conversation,
                    bound_workspace.context,
                    status,
                    self.build_imports_url(),
                )
