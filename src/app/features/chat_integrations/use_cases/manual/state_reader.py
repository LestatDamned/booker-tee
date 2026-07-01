from datetime import date
from decimal import Decimal
from uuid import UUID

from app.features.chat_integrations.errors import ChatManualOperationError
from app.features.chat_integrations.use_cases.manual.dto import (
    ChatManualCategoryChoice,
    ChatManualOperationConfirmation,
    ChatManualStoredAccount,
    ChatManualStoredCategory,
    StartedChatManualDateInput,
    StartedChatManualDateSelection,
    StartedChatManualDescriptionInput,
)
from app.features.ledger.models import OperationType


class ChatManualOperationStateReader:
    @staticmethod
    def read_account(payload: dict[str, object], account_index: int) -> ChatManualStoredAccount:
        account_ids = ChatManualOperationStateReader._read_list(payload, "account_ids")
        account_names = ChatManualOperationStateReader._read_list(payload, "account_names")
        account_currencies = ChatManualOperationStateReader._read_list(
            payload,
            "account_currencies",
        )
        if (
            account_index < 0
            or account_index >= len(account_ids)
            or account_index >= len(account_names)
            or account_index >= len(account_currencies)
        ):
            raise ChatManualOperationError("Selected account is no longer available.")
        try:
            account_id = UUID(str(account_ids[account_index]))
        except ValueError as exc:
            raise ChatManualOperationError("Stored account id is invalid.") from exc

        name = account_names[account_index]
        currency = account_currencies[account_index]
        if not isinstance(name, str) or not isinstance(currency, str):
            raise ChatManualOperationError("Stored account is invalid.")
        return ChatManualStoredAccount(id=account_id, name=name, currency=currency)

    @staticmethod
    def read_category(
        payload: dict[str, object],
        category_index: int,
    ) -> ChatManualStoredCategory:
        category_ids = ChatManualOperationStateReader._read_list(payload, "category_ids")
        category_names = ChatManualOperationStateReader._read_list(payload, "category_names")
        if (
            category_index < 0
            or category_index >= len(category_ids)
            or category_index >= len(category_names)
        ):
            raise ChatManualOperationError("Selected category is no longer available.")

        category_id = category_ids[category_index]
        parsed_category_id: UUID | None = None
        if category_id is not None:
            try:
                parsed_category_id = UUID(str(category_id))
            except ValueError as exc:
                raise ChatManualOperationError("Stored category id is invalid.") from exc

        category_name = category_names[category_index]
        if not isinstance(category_name, str):
            raise ChatManualOperationError("Stored category is invalid.")
        return ChatManualStoredCategory(id=parsed_category_id, name=category_name)

    @staticmethod
    def read_date_selection(
        payload: dict[str, object],
        *,
        action_token: str,
    ) -> StartedChatManualDateSelection:
        operation_type = OperationType(
            ChatManualOperationStateReader.read_required_string(payload, "operation_type")
        )
        return StartedChatManualDateSelection(
            action_token=action_token,
            operation_type=operation_type,
            amount=ChatManualOperationStateReader.read_amount(payload),
            currency=ChatManualOperationStateReader.read_required_string(payload, "currency"),
            account_name=ChatManualOperationStateReader.read_account_name_for_operation(
                payload,
                operation_type,
            ),
            destination_account_name=ChatManualOperationStateReader.read_optional_string(
                payload,
                "destination_account_name",
            ),
            source_message_id=ChatManualOperationStateReader.read_optional_string(
                payload,
                "source_message_id",
            ),
        )

    @staticmethod
    def read_date_input(
        payload: dict[str, object],
        *,
        action_token: str,
    ) -> StartedChatManualDateInput:
        date_selection = ChatManualOperationStateReader.read_date_selection(
            payload,
            action_token=action_token,
        )
        return StartedChatManualDateInput(
            operation_type=date_selection.operation_type,
            amount=date_selection.amount,
            currency=date_selection.currency,
            account_name=date_selection.account_name,
            destination_account_name=date_selection.destination_account_name,
            source_message_id=date_selection.source_message_id,
        )

    @staticmethod
    def read_description_input(
        payload: dict[str, object],
        *,
        action_token: str,
    ) -> StartedChatManualDescriptionInput:
        operation_type = OperationType(
            ChatManualOperationStateReader.read_required_string(payload, "operation_type")
        )
        operation_date = date.fromisoformat(
            ChatManualOperationStateReader.read_required_string(payload, "operation_date")
        )
        return StartedChatManualDescriptionInput(
            action_token=action_token,
            operation_type=operation_type,
            amount=ChatManualOperationStateReader.read_amount(payload),
            operation_date=operation_date,
            currency=ChatManualOperationStateReader.read_required_string(payload, "currency"),
            account_name=ChatManualOperationStateReader.read_account_name_for_operation(
                payload,
                operation_type,
            ),
            category_name=ChatManualOperationStateReader.read_optional_string(
                payload,
                "category_name",
            ),
            destination_account_name=ChatManualOperationStateReader.read_optional_string(
                payload,
                "destination_account_name",
            ),
            source_message_id=ChatManualOperationStateReader.read_optional_string(
                payload,
                "source_message_id",
            ),
        )

    @staticmethod
    def read_confirmation(
        payload: dict[str, object],
        *,
        action_token: str,
    ) -> ChatManualOperationConfirmation:
        operation_type = OperationType(
            ChatManualOperationStateReader.read_required_string(payload, "operation_type")
        )
        operation_date = date.fromisoformat(
            ChatManualOperationStateReader.read_required_string(payload, "operation_date")
        )
        amount = Decimal(ChatManualOperationStateReader.read_required_string(payload, "amount"))
        currency = ChatManualOperationStateReader.read_required_string(payload, "currency")

        if operation_type == OperationType.TRANSFER:
            return ChatManualOperationConfirmation(
                action_token=action_token,
                operation_type=operation_type,
                amount=amount,
                operation_date=operation_date,
                account_name=ChatManualOperationStateReader.read_required_string(
                    payload,
                    "source_account_name",
                ),
                currency=currency,
                destination_account_name=ChatManualOperationStateReader.read_required_string(
                    payload,
                    "destination_account_name",
                ),
                description=ChatManualOperationStateReader.read_optional_string(
                    payload,
                    "description",
                ),
                source_message_id=ChatManualOperationStateReader.read_optional_string(
                    payload,
                    "source_message_id",
                ),
            )

        return ChatManualOperationConfirmation(
            action_token=action_token,
            operation_type=operation_type,
            amount=amount,
            operation_date=operation_date,
            account_name=ChatManualOperationStateReader.read_required_string(
                payload,
                "account_name",
            ),
            currency=currency,
            category_name=ChatManualOperationStateReader.read_optional_string(
                payload,
                "category_name",
            ),
            description=ChatManualOperationStateReader.read_optional_string(
                payload,
                "description",
            ),
            source_message_id=ChatManualOperationStateReader.read_optional_string(
                payload,
                "source_message_id",
            ),
        )

    @staticmethod
    def read_category_choices(
        payload: dict[str, object],
    ) -> tuple[ChatManualCategoryChoice, ...]:
        category_ids = ChatManualOperationStateReader._read_list(payload, "category_ids")
        category_names = ChatManualOperationStateReader._read_list(payload, "category_names")
        if len(category_ids) != len(category_names):
            raise ChatManualOperationError("Stored manual operation categories are invalid.")

        choices: list[ChatManualCategoryChoice] = []
        for category_id, category_name in zip(category_ids, category_names, strict=True):
            parsed_category_id: UUID | None = None
            if category_id is not None:
                try:
                    parsed_category_id = UUID(str(category_id))
                except ValueError as exc:
                    raise ChatManualOperationError("Stored category id is invalid.") from exc
            if not isinstance(category_name, str):
                raise ChatManualOperationError("Stored category is invalid.")
            choices.append(ChatManualCategoryChoice(id=parsed_category_id, name=category_name))
        return tuple(choices)

    @staticmethod
    def read_account_name_for_operation(
        payload: dict[str, object],
        operation_type: OperationType,
    ) -> str:
        if operation_type == OperationType.TRANSFER:
            return ChatManualOperationStateReader.read_required_string(
                payload,
                "source_account_name",
            )
        return ChatManualOperationStateReader.read_required_string(payload, "account_name")

    @staticmethod
    def read_amount(payload: dict[str, object]) -> Decimal:
        return Decimal(ChatManualOperationStateReader.read_required_string(payload, "amount"))

    @staticmethod
    def read_optional_uuid(payload: dict[str, object], key: str) -> UUID | None:
        value = payload.get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ChatManualOperationError("Stored manual operation id is invalid.")
        try:
            return UUID(value)
        except ValueError as exc:
            raise ChatManualOperationError("Stored manual operation id is invalid.") from exc

    @staticmethod
    def read_required_uuid(payload: dict[str, object], key: str) -> UUID:
        value = ChatManualOperationStateReader.read_required_string(payload, key)
        try:
            return UUID(value)
        except ValueError as exc:
            raise ChatManualOperationError("Stored manual operation id is invalid.") from exc

    @staticmethod
    def read_required_string(payload: dict[str, object], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ChatManualOperationError("Stored manual operation is invalid.")
        return value

    @staticmethod
    def read_optional_string(payload: dict[str, object], key: str) -> str | None:
        value = payload.get(key)
        if value is None:
            return None
        return value if isinstance(value, str) else None

    @staticmethod
    def _read_list(payload: dict[str, object], key: str) -> list[object]:
        value = payload.get(key)
        if not isinstance(value, list):
            raise ChatManualOperationError("Stored manual operation is invalid.")
        return list(value)
