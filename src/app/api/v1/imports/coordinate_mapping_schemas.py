from typing import Literal
from uuid import UUID

from app.api.schemas import ApiModel, ApiRequestModel
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.mapping.coordinate_dto import (
    CoordinateControlRegion,
    CoordinateMappingSpec,
)


class CoordinatePreviewApiRequest(ApiRequestModel):
    spec: CoordinateMappingSpec
    control_regions: tuple[CoordinateControlRegion, ...] = ()


class CoordinateImportApiRequest(ApiRequestModel):
    spec: CoordinateMappingSpec
    control_regions: tuple[CoordinateControlRegion, ...] = ()
    template_name: str | None = None


class CoordinateImportTargetApiResponse(ApiModel):
    kind: Literal["import_review"]
    document_id: UUID


class CoordinateImportApiResponse(ApiModel):
    document_id: UUID
    status: UploadedDocumentStatus
    imported_row_count: int
    template_id: UUID | None
    replayed: bool
    review_target: CoordinateImportTargetApiResponse
