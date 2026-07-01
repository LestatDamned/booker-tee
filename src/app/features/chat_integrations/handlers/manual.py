from sqlalchemy.ext.asyncio import AsyncSession

from app.features.chat_integrations.actions.manual import (
    ChatManualAccountSelection,
    ChatManualCategoryPageSelection,
    ChatManualCategorySelection,
    ChatManualConfirmationSelection,
    ChatManualCorrectionSelection,
    ChatManualDateSelection,
    ChatManualDescriptionSelection,
)
from app.features.chat_integrations.errors import ChatManualOperationError
from app.features.chat_integrations.presentation.manual import TelegramManualPresenter
from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage
from app.features.chat_integrations.use_cases.manual.dto import (
    ChatManualOperationConfirmation,
    StartedChatManualAccountSelection,
    StartedChatManualAmountInput,
    StartedChatManualCategorySelection,
    StartedChatManualCorrectionSelection,
    StartedChatManualDateInput,
    StartedChatManualDateSelection,
    StartedChatManualDescriptionInput,
)
from app.features.chat_integrations.use_cases.manual.operations import ChatManualOperationService
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace
from app.features.ledger.models import OperationType

type ChatManualNextStep = (
    ChatManualOperationConfirmation
    | StartedChatManualAmountInput
    | StartedChatManualCategorySelection
    | StartedChatManualCorrectionSelection
    | StartedChatManualDateInput
    | StartedChatManualDateSelection
    | StartedChatManualDescriptionInput
)


class ChatManualEventHandler:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start_income_expense(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        operation_type: OperationType,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        try:
            selection = await ChatManualOperationService(self.session).start_income_expense(
                context=bound_workspace.context,
                operation_type=operation_type,
                source_message_id=event.source_message_id,
            )
        except ChatManualOperationError as exc:
            return TelegramManualPresenter.show_error(
                event.conversation,
                str(exc),
            )
        return TelegramManualPresenter.show_account_menu(event.conversation, selection)

    async def start_transfer(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        try:
            selection = await ChatManualOperationService(self.session).start_transfer(
                context=bound_workspace.context,
                source_message_id=event.source_message_id,
            )
        except ChatManualOperationError as exc:
            return TelegramManualPresenter.show_error(
                event.conversation,
                str(exc),
            )
        return TelegramManualPresenter.show_account_menu(event.conversation, selection)

    async def select_account(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatManualAccountSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        try:
            result = await ChatManualOperationService(self.session).select_account(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatManualOperationError as exc:
            return TelegramManualPresenter.show_error(
                event.conversation,
                str(exc),
            )
        if isinstance(result, StartedChatManualAccountSelection):
            return TelegramManualPresenter.show_account_menu(
                event.conversation,
                result,
            )
        return TelegramManualPresenter.show_amount_prompt(event.conversation, result)

    async def select_category(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatManualCategorySelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        try:
            next_step = await ChatManualOperationService(self.session).select_category(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatManualOperationError as exc:
            return TelegramManualPresenter.show_error(
                event.conversation,
                str(exc),
            )
        return self.show_next_step(event, next_step)

    async def change_category_page(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatManualCategoryPageSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        try:
            next_step = await ChatManualOperationService(self.session).change_category_page(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatManualOperationError as exc:
            return TelegramManualPresenter.show_error(
                event.conversation,
                str(exc),
            )
        return self.show_next_step(event, next_step)

    async def select_correction(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatManualCorrectionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        try:
            next_step = await ChatManualOperationService(self.session).select_correction(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatManualOperationError as exc:
            return TelegramManualPresenter.show_error(
                event.conversation,
                str(exc),
            )
        return self.show_next_step(event, next_step)

    async def skip_description(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatManualDescriptionSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        try:
            confirmation = await ChatManualOperationService(self.session).skip_description(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatManualOperationError as exc:
            return TelegramManualPresenter.show_error(
                event.conversation,
                str(exc),
            )
        return TelegramManualPresenter.show_confirmation(
            event.conversation,
            confirmation,
        )

    async def select_date(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatManualDateSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        try:
            next_step = await ChatManualOperationService(self.session).select_date(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatManualOperationError as exc:
            return TelegramManualPresenter.show_error(
                event.conversation,
                str(exc),
            )
        return self.show_next_step(event, next_step)

    async def answer_text_input(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        try:
            next_step = await ChatManualOperationService(
                self.session,
            ).continue_from_text_input(
                context=bound_workspace.context,
                text=event.text,
            )
        except ChatManualOperationError as exc:
            if "дат" in str(exc).casefold():
                return TelegramManualPresenter.show_date_error(
                    event.conversation,
                    str(exc),
                )
            return TelegramManualPresenter.show_amount_error(
                event.conversation,
                str(exc),
            )
        if next_step is None:
            return None
        return self.show_next_step(event, next_step)

    async def confirm_operation(
        self,
        event: InboundChatEvent,
        bound_workspace: BoundChatWorkspace,
        selection: ChatManualConfirmationSelection,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        try:
            result = await ChatManualOperationService(self.session).confirm(
                context=bound_workspace.context,
                selection=selection,
            )
        except ChatManualOperationError as exc:
            return TelegramManualPresenter.show_error(
                event.conversation,
                str(exc),
            )
        return TelegramManualPresenter.show_completed(event.conversation, result)

    @staticmethod
    def show_next_step(
        event: InboundChatEvent,
        next_step: ChatManualNextStep,
    ) -> OutboundChatMessage | None:
        if event.conversation is None:
            return None
        if isinstance(next_step, StartedChatManualAmountInput):
            return TelegramManualPresenter.show_amount_prompt(
                event.conversation,
                next_step,
            )
        if isinstance(next_step, StartedChatManualDateSelection):
            return TelegramManualPresenter.show_date_menu(event.conversation, next_step)
        if isinstance(next_step, StartedChatManualDateInput):
            return TelegramManualPresenter.show_date_input_prompt(
                event.conversation,
                next_step,
            )
        if isinstance(next_step, StartedChatManualCategorySelection):
            return TelegramManualPresenter.show_category_menu(
                event.conversation,
                next_step,
            )
        if isinstance(next_step, StartedChatManualDescriptionInput):
            return TelegramManualPresenter.show_description_prompt(
                event.conversation,
                next_step,
            )
        if isinstance(next_step, StartedChatManualCorrectionSelection):
            return TelegramManualPresenter.show_correction_menu(
                event.conversation,
                next_step,
            )
        return TelegramManualPresenter.show_confirmation(event.conversation, next_step)
