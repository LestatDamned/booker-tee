from app.features.accounts.service import AccountService
from app.features.chat_integrations.actions.manual import ChatManualAccountSelection
from app.features.chat_integrations.errors import ChatManualOperationError
from app.features.chat_integrations.models import ChatConversationFlow, ChatConversationState
from app.features.chat_integrations.use_cases.manual.builders import (
    ChatManualAccountChoiceBuilder,
    ChatManualOperationFlowMapper,
    ChatManualOperationPayloadBuilder,
)
from app.features.chat_integrations.use_cases.manual.dto import (
    StartedChatManualAccountSelection,
    StartedChatManualAmountInput,
)
from app.features.chat_integrations.use_cases.manual.state_reader import (
    ChatManualOperationStateReader,
)
from app.features.chat_integrations.use_cases.manual.state_store import (
    ChatManualOperationStateStore,
)
from app.features.ledger.models import OperationType
from app.features.workspaces.service import WorkspaceContext


class ChatManualAccountSelectionService:
    def __init__(
        self,
        *,
        states: ChatManualOperationStateStore,
        accounts: AccountService,
    ) -> None:
        self.states = states
        self.accounts = accounts

    async def select_account(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualAccountSelection,
    ) -> StartedChatManualAccountSelection | StartedChatManualAmountInput:
        state = await self.states.get_by_token(
            context=context,
            action_token=selection.action_token,
        )
        if state.step == "choose_account":
            return await self._select_income_expense_account(
                context=context,
                state=state,
                selection=selection,
            )

        if state.step == "choose_source_account":
            return await self._select_transfer_source_account(
                context=context,
                state=state,
                selection=selection,
            )

        if state.step == "choose_destination_account":
            return await self._select_transfer_destination_account(
                context=context,
                state=state,
                selection=selection,
            )

        raise ChatManualOperationError("Stored manual operation step is invalid.")

    async def _select_income_expense_account(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        selection: ChatManualAccountSelection,
    ) -> StartedChatManualAmountInput:
        account = ChatManualOperationStateReader.read_account(
            state.state_payload,
            selection.account_index,
        )
        flow = state.flow
        await self.states.replace(
            context=context,
            state=state,
            flow=flow,
            step="enter_amount",
            payload={
                "operation_type": ChatManualOperationFlowMapper.to_operation_type(flow).value,
                "account_id": str(account.id),
                "account_name": account.name,
                "currency": account.currency,
            },
        )
        return StartedChatManualAmountInput(
            operation_type=ChatManualOperationFlowMapper.to_operation_type(flow),
            account_name=account.name,
            currency=account.currency,
        )

    async def _select_transfer_source_account(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        selection: ChatManualAccountSelection,
    ) -> StartedChatManualAccountSelection:
        source_account = ChatManualOperationStateReader.read_account(
            state.state_payload,
            selection.account_index,
        )
        accounts = await self.accounts.list_active_accounts(context.workspace.id)
        destination_accounts = [
            account
            for account in accounts
            if account.id != source_account.id and account.currency == source_account.currency
        ]
        account_choices = ChatManualAccountChoiceBuilder.build_choices(destination_accounts)
        if not account_choices:
            raise ChatManualOperationError("Нет второго счета в той же валюте.")

        action_token = await self.states.replace(
            context=context,
            state=state,
            flow=ChatConversationFlow.RECORD_TRANSFER,
            step="choose_destination_account",
            payload={
                "source_account_id": str(source_account.id),
                "source_account_name": source_account.name,
                "currency": source_account.currency,
                **ChatManualOperationPayloadBuilder.accounts_payload(destination_accounts),
            },
        )
        return StartedChatManualAccountSelection(
            action_token=action_token,
            operation_type=OperationType.TRANSFER,
            account_choices=account_choices,
            source_account_name=source_account.name,
        )

    async def _select_transfer_destination_account(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        selection: ChatManualAccountSelection,
    ) -> StartedChatManualAmountInput:
        destination_account = ChatManualOperationStateReader.read_account(
            state.state_payload,
            selection.account_index,
        )
        source_account_name = ChatManualOperationStateReader.read_required_string(
            state.state_payload,
            "source_account_name",
        )
        source_account_id = ChatManualOperationStateReader.read_required_uuid(
            state.state_payload,
            "source_account_id",
        )
        currency = ChatManualOperationStateReader.read_required_string(
            state.state_payload,
            "currency",
        )
        await self.states.replace(
            context=context,
            state=state,
            flow=ChatConversationFlow.RECORD_TRANSFER,
            step="enter_amount",
            payload={
                "operation_type": OperationType.TRANSFER.value,
                "source_account_id": str(source_account_id),
                "source_account_name": source_account_name,
                "destination_account_id": str(destination_account.id),
                "destination_account_name": destination_account.name,
                "currency": currency,
            },
        )
        return StartedChatManualAmountInput(
            operation_type=OperationType.TRANSFER,
            account_name=source_account_name,
            currency=currency,
            destination_account_name=destination_account.name,
        )
