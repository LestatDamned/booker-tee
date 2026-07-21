from uuid import UUID

from pydantic import Field

from app.api.schemas import ApiRequestModel
from app.features.categories.models import CategoryKind
from app.features.ledger.domain.types import OperationType


class ImportReviewDraftEvaluationApiRequest(ApiRequestModel):
    operation_type: OperationType | None = None
    category_id: UUID | None = None
    property_id: UUID | None = None


class ImportReviewCategoryCreateApiRequest(ApiRequestModel):
    name: str = Field(max_length=255)
    kind: CategoryKind
