from dataclasses import dataclass
from enum import StrEnum


class OperationType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"


class OperationStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    CONFIRMED = "confirmed"
    IGNORED = "ignored"
    DUPLICATE = "duplicate"


class OperationSource(StrEnum):
    MANUAL = "manual"
    BANK_PDF = "bank_pdf"
    SYSTEM = "system"
    DEBT = "debt"


@dataclass(frozen=True)
class ManualOperationActions:
    can_edit: bool
    can_cancel: bool
    can_restore: bool
    can_delete: bool


def manual_operation_actions(status: OperationStatus) -> ManualOperationActions:
    return ManualOperationActions(
        can_edit=status in {OperationStatus.CONFIRMED, OperationStatus.DRAFT},
        can_cancel=status == OperationStatus.CONFIRMED,
        can_restore=status == OperationStatus.IGNORED,
        can_delete=status in {OperationStatus.DRAFT, OperationStatus.IGNORED},
    )


@dataclass(frozen=True)
class ImportedOperationActions:
    can_edit_review_fields: bool


def imported_operation_actions(status: OperationStatus) -> ImportedOperationActions:
    return ImportedOperationActions(
        can_edit_review_fields=status == OperationStatus.CONFIRMED,
    )
