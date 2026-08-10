from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.api.schemas import ApiRequestModel
from app.features.categories.models import CategoryKind
from app.features.import_review.domain.lifecycle import ImportReviewLifecycleAction
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.domain.types import OperationType


class ImportReviewDraftEvaluationApiRequest(ApiRequestModel):
    operation_type: OperationType | None = None
    category_id: UUID | None = None
    property_id: UUID | None = None


class ImportReviewCategoryCreateApiRequest(ApiRequestModel):
    name: str = Field(max_length=255)
    kind: CategoryKind


class ImportReviewNewTransferApiRequest(ApiRequestModel):
    kind: Literal["new_transfer"]
    counterparty_account_id: UUID


class ImportReviewRawRowMatchApiRequest(ApiRequestModel):
    kind: Literal["raw_row_match"]
    matched_item_id: UUID


class ImportReviewExistingTransferLinkApiRequest(ApiRequestModel):
    kind: Literal["existing_operation_link"]
    operation_id: UUID


ImportReviewTransferApiRequest = Annotated[
    ImportReviewNewTransferApiRequest
    | ImportReviewRawRowMatchApiRequest
    | ImportReviewExistingTransferLinkApiRequest,
    Field(discriminator="kind"),
]


class ImportReviewLifecycleApiRequest(ApiRequestModel):
    action: ImportReviewLifecycleAction
    expected_status: RawTransactionStatus


class ImportReviewExistingOperationLinkApiRequest(ApiRequestModel):
    operation_id: UUID
    expected_status: RawTransactionStatus


class ImportReviewConfirmationApiRequest(ApiRequestModel):
    operation_type: OperationType
    category_id: UUID
    property_id: UUID | None = None
    expected_status: RawTransactionStatus
    remember_rule: bool = False
    rule_pattern: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_confirmation(self) -> "ImportReviewConfirmationApiRequest":
        if self.operation_type not in {OperationType.INCOME, OperationType.EXPENSE}:
            raise ValueError("Confirmation supports only income or expense.")
        if self.rule_pattern is not None and not self.remember_rule:
            raise ValueError("rulePattern requires rememberRule=true.")
        if self.remember_rule and not (self.rule_pattern or "").strip():
            raise ValueError("rulePattern is required when rememberRule=true.")
        return self


class ImportReviewUndoApiRequest(ApiRequestModel):
    expected_operation_id: UUID
