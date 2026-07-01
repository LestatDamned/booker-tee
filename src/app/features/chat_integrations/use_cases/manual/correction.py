from decimal import Decimal

from app.features.categories.service import CategoryService
from app.features.chat_integrations.actions.manual import (
    ChatManualCorrectionCallbackData,
    ChatManualCorrectionSelection,
)
from app.features.chat_integrations.errors import ChatManualOperationError
from app.features.chat_integrations.models import ChatConversationState
from app.features.chat_integrations.use_cases.manual.builders import (
    ChatManualCategoryChoiceBuilder,
)
from app.features.chat_integrations.use_cases.manual.dto import (
    StartedChatManualAmountInput,
    StartedChatManualCategorySelection,
    StartedChatManualCorrectionSelection,
    StartedChatManualDateSelection,
    StartedChatManualDescriptionInput,
)
from app.features.chat_integrations.use_cases.manual.state_reader import (
    ChatManualOperationStateReader,
)
from app.features.chat_integrations.use_cases.manual.state_store import (
    ChatManualOperationStateStore,
)
from app.features.ledger.models import OperationType
from app.features.workspaces.service import WorkspaceContext

type ChatManualCorrectionResult = (
    StartedChatManualAmountInput
    | StartedChatManualCategorySelection
    | StartedChatManualCorrectionSelection
    | StartedChatManualDateSelection
    | StartedChatManualDescriptionInput
)


class ChatManualCorrectionService:
    def __init__(
        self,
        *,
        states: ChatManualOperationStateStore,
        categories: CategoryService,
    ) -> None:
        self.states = states
        self.categories = categories

    async def select_correction(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualCorrectionSelection,
    ) -> ChatManualCorrectionResult:
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

        if selection.correction_action == ChatManualCorrectionCallbackData.MENU_ACTION:
            return StartedChatManualCorrectionSelection(
                action_token=selection.action_token,
                confirmation=confirmation,
            )

        if selection.correction_action == ChatManualCorrectionCallbackData.AMOUNT_ACTION:
            await self.states.replace(
                context=context,
                state=state,
                flow=state.flow,
                step="enter_amount",
                payload=state.state_payload,
            )
            return StartedChatManualAmountInput(
                operation_type=confirmation.operation_type,
                account_name=confirmation.account_name,
                currency=confirmation.currency,
                destination_account_name=confirmation.destination_account_name,
            )

        if selection.correction_action == ChatManualCorrectionCallbackData.DATE_ACTION:
            action_token = await self.states.replace(
                context=context,
                state=state,
                flow=state.flow,
                step="choose_date",
                payload=state.state_payload,
            )
            return ChatManualOperationStateReader.read_date_selection(
                state.state_payload,
                action_token=action_token,
            )

        if selection.correction_action == ChatManualCorrectionCallbackData.CATEGORY_ACTION:
            return await self._select_category_correction(
                context=context,
                state=state,
                operation_type=confirmation.operation_type,
                amount=confirmation.amount,
                currency=confirmation.currency,
                account_name=confirmation.account_name,
            )

        if selection.correction_action == ChatManualCorrectionCallbackData.DESCRIPTION_ACTION:
            return await self._select_description_correction(
                context=context,
                state=state,
            )

        raise ChatManualOperationError("Выбери, что исправить, кнопкой.")

    async def _select_category_correction(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        operation_type: OperationType,
        amount: Decimal,
        currency: str,
        account_name: str,
    ) -> StartedChatManualCategorySelection:
        if operation_type == OperationType.TRANSFER:
            raise ChatManualOperationError("У перевода нет категории.")

        categories = await self.categories.list_or_seed_defaults(
            context.workspace.id,
            getattr(context.workspace, "type", None),
            include_inactive=False,
        )
        category_choices = ChatManualCategoryChoiceBuilder.build_choices(
            operation_type=operation_type,
            categories=categories,
        )
        action_token = await self.states.replace(
            context=context,
            state=state,
            flow=state.flow,
            step="choose_category",
            payload={
                **state.state_payload,
                "category_ids": [
                    str(choice.id) if choice.id is not None else None for choice in category_choices
                ],
                "category_names": [choice.name for choice in category_choices],
            },
        )
        return StartedChatManualCategorySelection(
            action_token=action_token,
            operation_type=operation_type,
            amount=amount,
            currency=currency,
            account_name=account_name,
            category_choices=category_choices,
        )

    async def _select_description_correction(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
    ) -> StartedChatManualDescriptionInput:
        action_token = await self.states.replace(
            context=context,
            state=state,
            flow=state.flow,
            step="enter_description",
            payload=state.state_payload,
        )
        return ChatManualOperationStateReader.read_description_input(
            state.state_payload,
            action_token=action_token,
        )
