from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError, api_error_responses
from app.api.v1.import_review.dependencies import get_import_review_reader
from app.api.v1.import_review.mapping import ImportReviewResponseMapper
from app.api.v1.import_review.schemas.responses import ImportReviewApiResponse
from app.features.imports.application.review.read_model import ImportReviewReader
from app.features.workspaces.permissions import permission_flags_for

router = APIRouter(prefix="/import-review", tags=["import-review"])


@router.get(
    "/{document_id}",
    response_model=ImportReviewApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
)
async def get_import_review(
    document_id: UUID,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    reader: Annotated[ImportReviewReader, Depends(get_import_review_reader)],
) -> ImportReviewApiResponse:
    permissions = permission_flags_for(context.workspace.membership)
    review = await reader.read(
        workspace_id=context.workspace.workspace.id,
        document_id=document_id,
        can_write=(permissions.can_manage_imports and permissions.can_write_financial_data),
    )
    if review is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="import_review_not_found",
            message="Документ для проверки не найден.",
        )
    return ImportReviewResponseMapper.response(review)
