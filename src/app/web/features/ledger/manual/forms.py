from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

from app.features.ledger.application.commands import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
    UpdateManualOperationCommand,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.models import OperationType

EDITABLE_OPERATION_TYPES = {
    OperationType.INCOME,
    OperationType.EXPENSE,
    OperationType.TRANSFER,
}


class ManualLedgerFormInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    version: str = ""
    operation_type: str = ""
    account_id: str = ""
    destination_account_id: str = ""
    amount: str = ""
    operation_date: str = ""
    category_id: str = ""
    property_id: str = ""
    description: str = ""
    return_to: str = ""


@dataclass(frozen=True)
class ManualLedgerFormIssue:
    field: str
    message: str


class ParsedManualLedgerForm(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    operation_type: OperationType
    account_id: UUID
    destination_account_id: UUID | None
    amount: Decimal
    operation_date: date
    category_id: UUID | None
    property_id: UUID | None
    description: str

    @field_validator("operation_type")
    @classmethod
    def require_editable_operation_type(
        cls,
        operation_type: OperationType,
    ) -> OperationType:
        if operation_type not in EDITABLE_OPERATION_TYPES:
            raise PydanticCustomError(
                "editable_operation_type",
                "Выберите тип операции.",
            )
        return operation_type

    @field_validator(
        "destination_account_id",
        "category_id",
        "property_id",
        mode="before",
    )
    @classmethod
    def empty_optional_reference_as_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("destination_account_id")
    @classmethod
    def validate_destination_account(
        cls,
        destination_account_id: UUID | None,
        info: ValidationInfo,
    ) -> UUID | None:
        operation_type = info.data.get("operation_type")
        if operation_type != OperationType.TRANSFER:
            return None
        if destination_account_id is None:
            raise PydanticCustomError(
                "destination_account_required",
                "Выберите счёт назначения.",
            )
        if destination_account_id == info.data.get("account_id"):
            raise PydanticCustomError(
                "different_transfer_accounts",
                "Счета перевода должны отличаться.",
            )
        return destination_account_id

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().replace(",", ".")
        return value

    @field_validator("amount")
    @classmethod
    def require_positive_amount(cls, amount: Decimal) -> Decimal:
        if not amount.is_finite() or amount <= Decimal("0"):
            raise PydanticCustomError(
                "positive_amount",
                "Сумма должна быть больше нуля.",
            )
        return amount


class ParsedManualLedgerEditForm(ParsedManualLedgerForm):
    version: int

    @field_validator("version")
    @classmethod
    def require_current_version(cls, version: int) -> int:
        if version < 1:
            raise PydanticCustomError(
                "current_operation_version",
                "Версия формы устарела или повреждена. Загрузите операцию заново.",
            )
        return version


@dataclass(frozen=True)
class ManualLedgerEditValidation:
    submission: ManualLedgerFormInput
    issues: tuple[ManualLedgerFormIssue, ...]
    command: UpdateManualOperationCommand | None

    @property
    def is_valid(self) -> bool:
        return self.command is not None and not self.issues

    @classmethod
    def from_form_input(
        cls,
        *,
        operation_id: UUID,
        form_input: ManualLedgerFormInput,
    ) -> Self:
        try:
            parsed = ParsedManualLedgerEditForm.model_validate(form_input.model_dump())
        except ValidationError as error:
            return cls(
                submission=form_input,
                issues=pydantic_form_issues(error),
                command=None,
            )
        return cls(
            submission=form_input,
            issues=(),
            command=UpdateManualOperationCommand(
                operation_id=operation_id,
                operation_type=parsed.operation_type,
                account_id=parsed.account_id,
                amount=parsed.amount,
                operation_date=parsed.operation_date,
                description=parsed.description,
                category_id=parsed.category_id,
                property_id=parsed.property_id,
                destination_account_id=parsed.destination_account_id,
                expected_version=parsed.version,
            ),
        )


type ManualLedgerCreateCommand = CreateManualIncomeExpenseCommand | CreateManualTransferCommand


@dataclass(frozen=True)
class ManualLedgerCreateValidation:
    submission: ManualLedgerFormInput
    issues: tuple[ManualLedgerFormIssue, ...]
    command: ManualLedgerCreateCommand | None

    @property
    def is_valid(self) -> bool:
        return self.command is not None and not self.issues

    @classmethod
    def from_form_input(
        cls,
        *,
        form_input: ManualLedgerFormInput,
    ) -> Self:
        try:
            parsed = ParsedManualLedgerForm.model_validate(form_input.model_dump())
        except ValidationError as error:
            return cls(
                submission=form_input,
                issues=pydantic_form_issues(error),
                command=None,
            )

        if parsed.operation_type == OperationType.TRANSFER:
            destination_account_id = parsed.destination_account_id
            if destination_account_id is None:
                raise RuntimeError("Valid transfer submission has no destination account.")
            command: ManualLedgerCreateCommand = CreateManualTransferCommand(
                source_account_id=parsed.account_id,
                destination_account_id=destination_account_id,
                amount=parsed.amount,
                operation_date=parsed.operation_date,
                description=parsed.description,
            )
        else:
            command = CreateManualIncomeExpenseCommand(
                operation_type=parsed.operation_type,
                account_id=parsed.account_id,
                amount=parsed.amount,
                operation_date=parsed.operation_date,
                description=parsed.description,
                category_id=parsed.category_id,
                property_id=parsed.property_id,
            )
        return cls(
            submission=form_input,
            issues=(),
            command=command,
        )


def pydantic_form_issues(error: ValidationError) -> tuple[ManualLedgerFormIssue, ...]:
    return tuple(_pydantic_form_issue(details) for details in error.errors(include_url=False))


def _pydantic_form_issue(details: Mapping[str, Any]) -> ManualLedgerFormIssue:
    location = details.get("loc", ())
    field = str(location[-1]) if location else "form"
    error_type = str(details.get("type", ""))
    raw_value = details.get("input")

    if field == "version":
        return ManualLedgerFormIssue(
            "form",
            "Версия формы устарела или повреждена. Загрузите операцию заново.",
        )
    if field == "operation_type":
        return ManualLedgerFormIssue(field, "Выберите тип операции.")
    if field == "account_id":
        message = "Выберите счёт." if raw_value in (None, "") else "Выберите допустимое значение."
        return ManualLedgerFormIssue(field, message)
    if field == "amount":
        message = (
            str(details.get("msg"))
            if error_type == "positive_amount"
            else "Введите корректную сумму."
        )
        return ManualLedgerFormIssue(field, message)
    if field == "operation_date":
        return ManualLedgerFormIssue(field, "Выберите корректную дату.")
    if field in {"destination_account_id", "category_id", "property_id"}:
        message = (
            str(details.get("msg"))
            if error_type
            in {
                "destination_account_required",
                "different_transfer_accounts",
            }
            else "Выберите допустимое значение."
        )
        return ManualLedgerFormIssue(field, message)
    return ManualLedgerFormIssue("form", "Проверьте введённые значения.")


def business_error_message(error: LedgerPostingError) -> str:
    translations = {
        "Account is not available in this workspace.": (
            "Выбранный счёт недоступен в этом workspace."
        ),
        "Category is not available in this workspace.": (
            "Выбранная категория недоступна в этом workspace."
        ),
        "Property is not available in this workspace.": (
            "Выбранный объект недоступен в этом workspace."
        ),
        "Cross-currency transfers are not supported in the MVP.": (
            "Переводы между счетами в разных валютах пока не поддерживаются."
        ),
        "Transfer accounts must be different.": "Счета перевода должны отличаться.",
        "Amount must be positive.": "Сумма должна быть больше нуля.",
        "Manual operation was not found.": "Ручная операция не найдена.",
        "Only manual operations can be changed here.": (
            "Здесь можно изменять только ручные операции."
        ),
        "Only confirmed manual operations can be cancelled.": (
            "Отменить можно только подтверждённую ручную операцию."
        ),
        "Only cancelled manual operations can be restored.": (
            "Восстановить можно только отменённую ручную операцию."
        ),
        "Cancel a manual operation before deleting it.": (
            "Перед удалением отмените ручную операцию."
        ),
        "Manual operation changed after this edit form was loaded.": (
            "Операция уже изменилась в другом окне. Ваши значения не сохранены."
        ),
    }
    return translations.get(
        str(error),
        "Не удалось сохранить операцию. Проверьте значения и повторите.",
    )
