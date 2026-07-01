from decimal import Decimal

from app.features.accounts.models import Account
from app.features.categories.models import Category, CategoryKind
from app.features.chat_integrations.errors import ChatManualOperationError
from app.features.chat_integrations.models import ChatConversationFlow
from app.features.chat_integrations.use_cases.manual.config import (
    CHAT_MANUAL_ACCOUNT_MAX_CHOICES,
    CHAT_MANUAL_CATEGORY_PAGE_SIZE,
)
from app.features.chat_integrations.use_cases.manual.dto import (
    ChatManualAccountChoice,
    ChatManualCategoryChoice,
    StartedChatManualCategorySelection,
)
from app.features.ledger.models import OperationType


class ChatManualAccountChoiceBuilder:
    @staticmethod
    def build_choices(accounts: list[Account]) -> tuple[ChatManualAccountChoice, ...]:
        return tuple(
            ChatManualAccountChoice(name=account.name, currency=account.currency)
            for account in accounts[:CHAT_MANUAL_ACCOUNT_MAX_CHOICES]
        )


class ChatManualOperationPayloadBuilder:
    @staticmethod
    def accounts_payload(accounts: list[Account]) -> dict[str, object]:
        limited_accounts = accounts[:CHAT_MANUAL_ACCOUNT_MAX_CHOICES]
        return {
            "account_ids": [str(account.id) for account in limited_accounts],
            "account_names": [account.name for account in limited_accounts],
            "account_currencies": [account.currency for account in limited_accounts],
        }

    @staticmethod
    def source_message_payload(source_message_id: str | None) -> dict[str, object]:
        if source_message_id is None:
            return {}
        return {"source_message_id": source_message_id}


class ChatManualCategoryChoiceBuilder:
    @staticmethod
    def build_choices(
        *,
        operation_type: OperationType,
        categories: list[Category],
    ) -> tuple[ChatManualCategoryChoice, ...]:
        accepted_kinds = ChatManualCategoryChoiceBuilder._accepted_kinds(operation_type)
        excluded_system_keys = {"transfer", "adjustment", "duplicate", "ignore"}
        choices = [ChatManualCategoryChoice(id=None, name="Без категории")]

        for category in categories:
            if not category.is_active:
                continue
            if category.kind not in accepted_kinds:
                continue
            if category.system_key in excluded_system_keys:
                continue
            if category.system_key == "uncategorized":
                continue
            choices.append(ChatManualCategoryChoice(id=category.id, name=category.name))

        return tuple(choices)

    @staticmethod
    def _accepted_kinds(operation_type: OperationType) -> set[CategoryKind]:
        match operation_type:
            case OperationType.INCOME:
                return {CategoryKind.INCOME, CategoryKind.MIXED}
            case OperationType.EXPENSE:
                return {CategoryKind.EXPENSE, CategoryKind.MIXED}
            case _:
                return set()


class ChatManualCategoryPageBuilder:
    @staticmethod
    def build_selection(
        *,
        action_token: str,
        operation_type: OperationType,
        amount: Decimal,
        currency: str,
        account_name: str,
        category_choices: tuple[ChatManualCategoryChoice, ...],
        page_index: int,
        source_message_id: str | None = None,
    ) -> StartedChatManualCategorySelection:
        page_count = max(
            1,
            (len(category_choices) + CHAT_MANUAL_CATEGORY_PAGE_SIZE - 1)
            // CHAT_MANUAL_CATEGORY_PAGE_SIZE,
        )
        normalized_page_index = min(max(page_index, 0), page_count - 1)
        page_start_index = normalized_page_index * CHAT_MANUAL_CATEGORY_PAGE_SIZE
        page_end_index = page_start_index + CHAT_MANUAL_CATEGORY_PAGE_SIZE
        return StartedChatManualCategorySelection(
            action_token=action_token,
            operation_type=operation_type,
            amount=amount,
            currency=currency,
            account_name=account_name,
            category_choices=category_choices[page_start_index:page_end_index],
            page_index=normalized_page_index,
            page_count=page_count,
            page_start_index=page_start_index,
            source_message_id=source_message_id,
        )


class ChatManualOperationFlowMapper:
    @staticmethod
    def to_flow(operation_type: OperationType) -> ChatConversationFlow:
        match operation_type:
            case OperationType.EXPENSE:
                return ChatConversationFlow.RECORD_EXPENSE
            case OperationType.INCOME:
                return ChatConversationFlow.RECORD_INCOME
            case OperationType.TRANSFER:
                return ChatConversationFlow.RECORD_TRANSFER
            case _:
                raise ChatManualOperationError("Manual operation type is not supported.")

    @staticmethod
    def to_operation_type(flow: ChatConversationFlow) -> OperationType:
        match flow:
            case ChatConversationFlow.RECORD_EXPENSE:
                return OperationType.EXPENSE
            case ChatConversationFlow.RECORD_INCOME:
                return OperationType.INCOME
            case ChatConversationFlow.RECORD_TRANSFER:
                return OperationType.TRANSFER
            case _:
                raise ChatManualOperationError("Stored manual operation flow is invalid.")
