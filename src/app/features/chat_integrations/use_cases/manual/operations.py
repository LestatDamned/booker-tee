from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.service import AccountService
from app.features.categories.service import CategoryService
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
from app.features.chat_integrations.models import ChatConversationFlow
from app.features.chat_integrations.use_cases.manual.accounts import (
    ChatManualAccountSelectionService,
)
from app.features.chat_integrations.use_cases.manual.builders import (
    ChatManualAccountChoiceBuilder,
    ChatManualOperationFlowMapper,
    ChatManualOperationPayloadBuilder,
)
from app.features.chat_integrations.use_cases.manual.correction import (
    ChatManualCorrectionResult,
    ChatManualCorrectionService,
)
from app.features.chat_integrations.use_cases.manual.dto import (
    ChatManualOperationConfirmation,
    ChatManualOperationResult,
    StartedChatManualAccountSelection,
    StartedChatManualAmountInput,
    StartedChatManualCategorySelection,
    StartedChatManualDescriptionInput,
)
from app.features.chat_integrations.use_cases.manual.posting import ChatManualOperationPoster
from app.features.chat_integrations.use_cases.manual.progress import (
    ChatManualDateSelectionResult,
    ChatManualOperationProgressService,
    ChatManualTextInputResult,
)
from app.features.chat_integrations.use_cases.manual.state_reader import (
    ChatManualOperationStateReader,
)
from app.features.chat_integrations.use_cases.manual.state_store import (
    ChatManualOperationStateStore,
)
from app.features.ledger.application.manual_operations import ManualOperationUseCase
from app.features.ledger.domain.types import OperationType
from app.features.workspaces.service import WorkspaceContext


class ChatManualOperationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.accounts = AccountService(session)
        self.categories = CategoryService(session)
        self.manual_operations = ManualOperationUseCase(session)
        self.states = ChatManualOperationStateStore(session)
        self.account_selection = ChatManualAccountSelectionService(
            states=self.states,
            accounts=self.accounts,
        )
        self.corrections = ChatManualCorrectionService(
            states=self.states,
            categories=self.categories,
        )
        self.progress = ChatManualOperationProgressService(
            states=self.states,
            categories=self.categories,
        )
        self.operation_poster = ChatManualOperationPoster(self.manual_operations)

    async def start_income_expense(
        self,
        *,
        context: WorkspaceContext,
        operation_type: OperationType,
        source_message_id: str | None = None,
    ) -> StartedChatManualAccountSelection:
        if operation_type not in {OperationType.INCOME, OperationType.EXPENSE}:
            raise ChatManualOperationError("Manual operation must be income or expense.")

        accounts = await self.accounts.list_active_accounts(context.workspace.id)
        account_choices = ChatManualAccountChoiceBuilder.build_choices(accounts)
        if not account_choices:
            raise ChatManualOperationError("Сначала создай счет в Booker Tee.")

        action_token = await self.states.create(
            context=context,
            flow=ChatManualOperationFlowMapper.to_flow(operation_type),
            step="choose_account",
            payload={
                **ChatManualOperationPayloadBuilder.accounts_payload(accounts),
                **ChatManualOperationPayloadBuilder.source_message_payload(source_message_id),
            },
        )
        return StartedChatManualAccountSelection(
            action_token=action_token,
            operation_type=operation_type,
            account_choices=account_choices,
            source_message_id=source_message_id,
        )

    async def start_transfer(
        self,
        *,
        context: WorkspaceContext,
        source_message_id: str | None = None,
    ) -> StartedChatManualAccountSelection:
        accounts = await self.accounts.list_active_accounts(context.workspace.id)
        account_choices = ChatManualAccountChoiceBuilder.build_choices(accounts)
        if len(account_choices) < 2:
            raise ChatManualOperationError("Для перевода нужны минимум два активных счета.")

        action_token = await self.states.create(
            context=context,
            flow=ChatConversationFlow.RECORD_TRANSFER,
            step="choose_source_account",
            payload={
                **ChatManualOperationPayloadBuilder.accounts_payload(accounts),
                **ChatManualOperationPayloadBuilder.source_message_payload(source_message_id),
            },
        )
        return StartedChatManualAccountSelection(
            action_token=action_token,
            operation_type=OperationType.TRANSFER,
            account_choices=account_choices,
            source_message_id=source_message_id,
        )

    async def select_account(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualAccountSelection,
    ) -> StartedChatManualAccountSelection | StartedChatManualAmountInput:
        return await self.account_selection.select_account(
            context=context,
            selection=selection,
        )

    async def continue_from_text_input(
        self,
        *,
        context: WorkspaceContext,
        text: str | None,
    ) -> ChatManualTextInputResult:
        return await self.progress.continue_from_text_input(
            context=context,
            text=text,
        )

    async def select_date(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualDateSelection,
    ) -> ChatManualDateSelectionResult:
        return await self.progress.select_date(
            context=context,
            selection=selection,
        )

    async def select_category(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualCategorySelection,
    ) -> StartedChatManualDescriptionInput:
        return await self.progress.select_category(
            context=context,
            selection=selection,
        )

    async def change_category_page(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualCategoryPageSelection,
    ) -> StartedChatManualCategorySelection:
        return await self.progress.change_category_page(
            context=context,
            selection=selection,
        )

    async def skip_description(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualDescriptionSelection,
    ) -> ChatManualOperationConfirmation:
        return await self.progress.skip_description(
            context=context,
            selection=selection,
        )

    async def select_correction(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualCorrectionSelection,
    ) -> ChatManualCorrectionResult:
        return await self.corrections.select_correction(
            context=context,
            selection=selection,
        )

    async def confirm(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualConfirmationSelection,
    ) -> ChatManualOperationResult:
        state = await self.states.get_by_token(
            context=context,
            action_token=selection.action_token,
        )
        if state.step != "confirm":
            raise ChatManualOperationError("Stored manual operation step is invalid.")

        confirmation = ChatManualOperationStateReader.read_confirmation(
            state.state_payload,
            action_token=selection.action_token,
        )
        operation = await self.operation_poster.post(
            context=context,
            payload=state.state_payload,
            confirmation=confirmation,
        )

        await self.states.consume(state)
        return ChatManualOperationResult(
            operation_id=operation.id,
            operation_type=confirmation.operation_type,
            amount=confirmation.amount,
            currency=confirmation.currency,
            operation_date=confirmation.operation_date,
        )
