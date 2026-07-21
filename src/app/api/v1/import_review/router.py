from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError, api_error_responses
from app.api.v1.import_review.dependencies import (
    get_import_review_category_creator,
    get_import_review_draft_evaluator,
    get_import_review_reader,
    require_import_review_write_context,
)
from app.api.v1.import_review.mapping import ImportReviewResponseMapper
from app.api.v1.import_review.schemas.requests import (
    ImportReviewCategoryCreateApiRequest,
    ImportReviewDraftEvaluationApiRequest,
)
from app.api.v1.import_review.schemas.responses import (
    ImportReviewApiResponse,
    ImportReviewCategoryReferenceApiResponse,
    ImportReviewDraftEvaluationApiResponse,
)
from app.features.categories.service import CategoryError
from app.features.imports.application.review.classification import (
    ImportReviewCategoryCreator,
    ImportReviewDraftEvaluator,
    ImportReviewDraftValidationError,
)
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


@router.post(
    "/{document_id}/items/{item_id}/draft-evaluation",
    response_model=ImportReviewDraftEvaluationApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def evaluate_import_review_draft(
    document_id: UUID,
    item_id: UUID,
    request: ImportReviewDraftEvaluationApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_import_review_write_context),
    ],
    evaluator: Annotated[
        ImportReviewDraftEvaluator,
        Depends(get_import_review_draft_evaluator),
    ],
) -> ImportReviewDraftEvaluationApiResponse:
    try:
        evaluation = await evaluator.evaluate(
            workspace_id=context.workspace.workspace.id,
            document_id=document_id,
            item_id=item_id,
            operation_type=request.operation_type,
            category_id=request.category_id,
            property_id=request.property_id,
        )
    except ImportReviewDraftValidationError as exc:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="invalid_import_review_draft",
            message="Проверьте выбранные значения.",
            field_errors={exc.field: [str(exc)]},
        ) from exc
    if evaluation is None:
        raise _review_item_not_found()
    return ImportReviewResponseMapper.draft_evaluation(evaluation)


@router.post(
    "/{document_id}/items/{item_id}/categories",
    response_model=ImportReviewCategoryReferenceApiResponse,
    status_code=status.HTTP_201_CREATED,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def create_import_review_category(
    document_id: UUID,
    item_id: UUID,
    request: ImportReviewCategoryCreateApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_import_review_write_context),
    ],
    creator: Annotated[
        ImportReviewCategoryCreator,
        Depends(get_import_review_category_creator),
    ],
) -> ImportReviewCategoryReferenceApiResponse:
    try:
        category = await creator.create(
            workspace_id=context.workspace.workspace.id,
            document_id=document_id,
            item_id=item_id,
            name=request.name,
            kind=request.kind,
        )
    except CategoryError as exc:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="invalid_category",
            message="Категорию не удалось создать.",
            field_errors={"name": [str(exc)]},
        ) from exc
    if category is None:
        raise _review_item_not_found()
    return ImportReviewResponseMapper.category_reference(category)


def _review_item_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        code="import_review_item_not_found",
        message="Строка import review не найдена.",
    )
