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
