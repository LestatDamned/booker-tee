from datetime import date

from app.features.categories.service import CategoryService
from app.features.chat_integrations.actions.manual import (
    ChatManualCategoryPageSelection,
    ChatManualCategorySelection,
    ChatManualDateCallbackData,
    ChatManualDateSelection,
    ChatManualDescriptionSelection,
)
from app.features.chat_integrations.errors import ChatManualOperationError
from app.features.chat_integrations.models import ChatConversationState
from app.features.chat_integrations.use_cases.manual.builders import (
    ChatManualCategoryChoiceBuilder,
    ChatManualCategoryPageBuilder,
    ChatManualOperationFlowMapper,
)
from app.features.chat_integrations.use_cases.manual.dto import (
    ChatManualOperationConfirmation,
    StartedChatManualCategorySelection,
    StartedChatManualDateInput,
    StartedChatManualDateSelection,
    StartedChatManualDescriptionInput,
)
from app.features.chat_integrations.use_cases.manual.parsing import (
    ChatManualAmountParser,
    ChatManualDateParser,
    ChatManualDateResolver,
    ChatManualDescriptionCleaner,
)
from app.features.chat_integrations.use_cases.manual.state_reader import (
    ChatManualOperationStateReader,
)
from app.features.chat_integrations.use_cases.manual.state_store import (
    ChatManualOperationStateStore,
)
from app.features.ledger.models import OperationType
from app.features.workspaces.service import WorkspaceContext

type ChatManualTextInputResult = (
    ChatManualOperationConfirmation
    | StartedChatManualCategorySelection
    | StartedChatManualDateSelection
    | StartedChatManualDescriptionInput
    | None
)

type ChatManualDateSelectionResult = (
    StartedChatManualCategorySelection
    | StartedChatManualDateInput
    | StartedChatManualDescriptionInput
)


class ChatManualOperationProgressService:
    def __init__(
        self,
        *,
        states: ChatManualOperationStateStore,
        categories: CategoryService,
    ) -> None:
        self.states = states
        self.categories = categories

    async def continue_from_text_input(
        self,
        *,
        context: WorkspaceContext,
        text: str | None,
    ) -> ChatManualTextInputResult:
        state = await self.states.get_latest_active(context=context)
        if state is None:
            return None

        if state.step == "enter_amount":
            return await self._start_date_selection_from_amount(
                context=context,
                state=state,
                amount_text=text,
            )

        if state.step == "enter_custom_date":
            return await self._continue_after_operation_date(
                context=context,
                state=state,
                operation_date=ChatManualDateParser.parse(text),
            )

        if state.step == "enter_description":
            return await self._start_confirmation_from_description(
                context=context,
                state=state,
                description_text=text,
            )

        return None

    async def select_date(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualDateSelection,
    ) -> ChatManualDateSelectionResult:
        state = await self.states.get_by_token(
            context=context,
            action_token=selection.action_token,
        )
        if state.step != "choose_date":
            raise ChatManualOperationError("Stored manual operation step is invalid.")

        if selection.date_action == ChatManualDateCallbackData.CUSTOM_ACTION:
            action_token = await self.states.replace(
                context=context,
                state=state,
                flow=state.flow,
                step="enter_custom_date",
                payload=state.state_payload,
            )
            return ChatManualOperationStateReader.read_date_input(
                state.state_payload,
                action_token=action_token,
            )

        return await self._continue_after_operation_date(
            context=context,
            state=state,
            operation_date=ChatManualDateResolver.resolve(selection.date_action),
        )

    async def select_category(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualCategorySelection,
    ) -> StartedChatManualDescriptionInput:
        state = await self.states.get_by_token(
            context=context,
            action_token=selection.action_token,
        )
        if state.step != "choose_category":
            raise ChatManualOperationError("Stored manual operation step is invalid.")

        category = ChatManualOperationStateReader.read_category(
            state.state_payload,
            selection.category_index,
        )
        payload = {
            **state.state_payload,
            "category_id": str(category.id) if category.id is not None else None,
            "category_name": category.name,
        }
        return await self._start_description_input(
            context=context,
            state=state,
            payload=payload,
        )

    async def change_category_page(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualCategoryPageSelection,
    ) -> StartedChatManualCategorySelection:
        state = await self.states.get_by_token(
            context=context,
            action_token=selection.action_token,
        )
        if state.step != "choose_category":
            raise ChatManualOperationError("Stored manual operation step is invalid.")

        operation_type = ChatManualOperationFlowMapper.to_operation_type(state.flow)
        return ChatManualCategoryPageBuilder.build_selection(
            action_token=selection.action_token,
            operation_type=operation_type,
            amount=ChatManualOperationStateReader.read_amount(state.state_payload),
            currency=ChatManualOperationStateReader.read_required_string(
                state.state_payload,
                "currency",
            ),
            account_name=ChatManualOperationStateReader.read_account_name_for_operation(
                state.state_payload,
                operation_type,
            ),
            category_choices=ChatManualOperationStateReader.read_category_choices(
                state.state_payload,
            ),
            page_index=selection.page_index,
            source_message_id=ChatManualOperationStateReader.read_optional_string(
                state.state_payload,
                "source_message_id",
            ),
        )

    async def skip_description(
        self,
        *,
        context: WorkspaceContext,
        selection: ChatManualDescriptionSelection,
    ) -> ChatManualOperationConfirmation:
        state = await self.states.get_by_token(
            context=context,
            action_token=selection.action_token,
        )
        if state.step != "enter_description":
            raise ChatManualOperationError("Stored manual operation step is invalid.")

        return await self._start_confirmation_from_description(
            context=context,
            state=state,
            description_text=None,
        )

    async def _start_date_selection_from_amount(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        amount_text: str | None,
    ) -> StartedChatManualDateSelection:
        amount = ChatManualAmountParser.parse_positive_amount(amount_text)
        payload = {
            **state.state_payload,
            "amount": str(amount),
        }
        action_token = await self.states.replace(
            context=context,
            state=state,
            flow=state.flow,
            step="choose_date",
            payload=payload,
        )
        return ChatManualOperationStateReader.read_date_selection(
            payload,
            action_token=action_token,
        )

    async def _continue_after_operation_date(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        operation_date: date,
    ) -> StartedChatManualCategorySelection | StartedChatManualDescriptionInput:
        operation_type = ChatManualOperationFlowMapper.to_operation_type(state.flow)
        payload = {
            **state.state_payload,
            "operation_date": operation_date.isoformat(),
        }
        if operation_type != OperationType.TRANSFER:
            categories = await self.categories.list_or_seed_defaults(
                context.workspace.id,
                getattr(context.workspace, "type", None),
                include_inactive=False,
            )
            category_choices = ChatManualCategoryChoiceBuilder.build_choices(
                operation_type=operation_type,
                categories=categories,
            )
            if category_choices:
                action_token = await self.states.replace(
                    context=context,
                    state=state,
                    flow=state.flow,
                    step="choose_category",
                    payload={
                        **payload,
                        "category_ids": [
                            str(choice.id) if choice.id is not None else None
                            for choice in category_choices
                        ],
                        "category_names": [choice.name for choice in category_choices],
                    },
                )
                return ChatManualCategoryPageBuilder.build_selection(
                    action_token=action_token,
                    operation_type=operation_type,
                    amount=ChatManualOperationStateReader.read_amount(payload),
                    currency=ChatManualOperationStateReader.read_required_string(
                        payload,
                        "currency",
                    ),
                    account_name=ChatManualOperationStateReader.read_required_string(
                        payload,
                        "account_name",
                    ),
                    category_choices=category_choices,
                    page_index=0,
                    source_message_id=ChatManualOperationStateReader.read_optional_string(
                        payload,
                        "source_message_id",
                    ),
                )

        return await self._start_description_input(
            context=context,
            state=state,
            payload=payload,
        )

    async def _start_description_input(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        payload: dict[str, object],
    ) -> StartedChatManualDescriptionInput:
        action_token = await self.states.replace(
            context=context,
            state=state,
            flow=state.flow,
            step="enter_description",
            payload=payload,
        )
        return ChatManualOperationStateReader.read_description_input(
            payload,
            action_token=action_token,
        )

    async def _start_confirmation_from_description(
        self,
        *,
        context: WorkspaceContext,
        state: ChatConversationState,
        description_text: str | None,
    ) -> ChatManualOperationConfirmation:
        payload = {
            **state.state_payload,
            "description": ChatManualDescriptionCleaner.clean(description_text),
        }
        action_token = await self.states.replace(
            context=context,
            state=state,
            flow=state.flow,
            step="confirm",
            payload=payload,
        )
        return ChatManualOperationStateReader.read_confirmation(
            payload,
            action_token=action_token,
        )
