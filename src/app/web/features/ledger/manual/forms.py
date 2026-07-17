from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from app.features.ledger.application.commands import UpdateManualOperationCommand
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.models import OperationType

EDITABLE_OPERATION_TYPES = {
    OperationType.INCOME,
    OperationType.EXPENSE,
    OperationType.TRANSFER,
}


@dataclass(frozen=True)
class ManualLedgerEditSubmission:
    operation_type: str = ""
    account_id: str = ""
    destination_account_id: str = ""
    amount: str = ""
    operation_date: str = ""
    category_id: str = ""
    property_id: str = ""
    description: str = ""


@dataclass(frozen=True)
class ManualLedgerFormIssue:
    field: str
    message: str


@dataclass(frozen=True)
class ManualLedgerEditValidation:
    submission: ManualLedgerEditSubmission
    issues: tuple[ManualLedgerFormIssue, ...]
    command: UpdateManualOperationCommand | None

    @property
    def is_valid(self) -> bool:
        return self.command is not None and not self.issues


def validate_manual_ledger_edit(
    operation_id: UUID,
    submission: ManualLedgerEditSubmission,
) -> ManualLedgerEditValidation:
    issues: list[ManualLedgerFormIssue] = []
    operation_type = parse_operation_type(submission.operation_type, issues)
    account_id = parse_required_uuid(
        submission.account_id,
        field="account_id",
        required_message="Выберите счёт.",
        issues=issues,
    )
    amount = parse_positive_amount(submission.amount, issues)
    operation_date = parse_operation_date(submission.operation_date, issues)
    category_id = parse_optional_uuid(submission.category_id, "category_id", issues)
    property_id = parse_optional_uuid(submission.property_id, "property_id", issues)
    destination_account_id = parse_optional_uuid(
        submission.destination_account_id,
        "destination_account_id",
        issues,
    )

    if operation_type == OperationType.TRANSFER:
        if destination_account_id is None and not any(
            issue.field == "destination_account_id" for issue in issues
        ):
            issues.append(
                ManualLedgerFormIssue(
                    "destination_account_id",
                    "Выберите счёт назначения.",
                )
            )
        elif account_id is not None and destination_account_id == account_id:
            issues.append(
                ManualLedgerFormIssue(
                    "destination_account_id",
                    "Счета перевода должны отличаться.",
                )
            )
    else:
        destination_account_id = None

    if issues or operation_type is None or account_id is None or amount is None:
        return ManualLedgerEditValidation(submission, tuple(issues), None)
    if operation_date is None:
        return ManualLedgerEditValidation(submission, tuple(issues), None)

    return ManualLedgerEditValidation(
        submission=submission,
        issues=(),
        command=UpdateManualOperationCommand(
            operation_id=operation_id,
            operation_type=operation_type,
            account_id=account_id,
            amount=amount,
            operation_date=operation_date,
            description=submission.description,
            category_id=category_id,
            property_id=property_id,
            destination_account_id=destination_account_id,
        ),
    )


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
    }
    return translations.get(
        str(error),
        "Не удалось сохранить операцию. Проверьте значения и повторите.",
    )


def parse_operation_type(
    raw_value: str,
    issues: list[ManualLedgerFormIssue],
) -> OperationType | None:
    try:
        operation_type = OperationType(raw_value)
    except ValueError:
        issues.append(ManualLedgerFormIssue("operation_type", "Выберите тип операции."))
        return None
    if operation_type not in EDITABLE_OPERATION_TYPES:
        issues.append(ManualLedgerFormIssue("operation_type", "Выберите тип операции."))
        return None
    return operation_type


def parse_positive_amount(
    raw_value: str,
    issues: list[ManualLedgerFormIssue],
) -> Decimal | None:
    try:
        amount = Decimal(raw_value.strip().replace(",", "."))
    except InvalidOperation:
        issues.append(ManualLedgerFormIssue("amount", "Введите корректную сумму."))
        return None
    if not amount.is_finite() or amount <= Decimal("0"):
        issues.append(ManualLedgerFormIssue("amount", "Сумма должна быть больше нуля."))
        return None
    return amount


def parse_operation_date(
    raw_value: str,
    issues: list[ManualLedgerFormIssue],
) -> date | None:
    try:
        return date.fromisoformat(raw_value)
    except ValueError:
        issues.append(ManualLedgerFormIssue("operation_date", "Выберите корректную дату."))
        return None


def parse_required_uuid(
    raw_value: str,
    *,
    field: str,
    required_message: str,
    issues: list[ManualLedgerFormIssue],
) -> UUID | None:
    if not raw_value:
        issues.append(ManualLedgerFormIssue(field, required_message))
        return None
    return parse_optional_uuid(raw_value, field, issues)


def parse_optional_uuid(
    raw_value: str,
    field: str,
    issues: list[ManualLedgerFormIssue],
) -> UUID | None:
    if not raw_value:
        return None
    try:
        return UUID(raw_value)
    except ValueError:
        issues.append(ManualLedgerFormIssue(field, "Выберите допустимое значение."))
        return None
