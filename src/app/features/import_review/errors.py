"""Errors owned by the import-review feature."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.features.import_review.domain.classification import ReviewBlockingReasonCode


class RawTransactionReviewError(ValueError):
    pass


class ImportReviewDraftValidationError(ValueError):
    def __init__(self, *, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


class ImportReviewRuleApplicationNotFoundError(ValueError):
    """Raised when the review document is outside the current workspace."""


class ImportReviewConfirmationError(ValueError):
    pass


class ImportReviewConfirmationConflictError(ImportReviewConfirmationError):
    pass


class ImportReviewConfirmationValidationError(ImportReviewConfirmationError):
    def __init__(
        self,
        *,
        blocking_reason_codes: tuple[ReviewBlockingReasonCode, ...] = (),
        field_errors: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__("Import review confirmation is not valid.")
        self.blocking_reason_codes = blocking_reason_codes
        self.field_errors = field_errors or {}


class ImportReviewLifecycleError(ValueError):
    pass


class ImportReviewLifecycleConflictError(ImportReviewLifecycleError):
    pass
