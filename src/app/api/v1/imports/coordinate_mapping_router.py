from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import ApiRequestContext, require_api_raw_import_read_context
from app.api.errors import ApiError, api_error_responses
from app.api.v1.imports.coordinate_mapping_schemas import (
    CoordinateImportApiRequest,
    CoordinateImportApiResponse,
    CoordinateImportTargetApiResponse,
    CoordinatePreviewApiRequest,
)
from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.imports.mapping.coordinate_dto import CoordinateMappingOverview, CoordinatePreview
from app.features.imports.mapping.coordinate_pdf import CoordinatePdfError
from app.features.imports.mapping.coordinate_service import (
    CoordinateMappingImportService,
    CoordinateMappingService,
)
from app.features.imports.mapping.errors import (
    MappingImportIdempotencyConflictError,
    MappingImportNotFoundError,
    MappingImportUnavailableError,
    UnknownStatementMappingError,
)
from app.features.workspaces.permissions import can_manage_imports

router = APIRouter()


def _service(session: AsyncSession, settings: Settings) -> CoordinateMappingService:
    return CoordinateMappingService(session, settings)


@router.get(
    "/documents/{document_id}/coordinate-mapping",
    response_model=CoordinateMappingOverview,
    responses=api_error_responses(401, 403, 404, 409),
)
async def get_coordinate_mapping(
    document_id: UUID,
    context: Annotated[ApiRequestContext, Depends(require_api_raw_import_read_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CoordinateMappingOverview:
    try:
        result = await _service(session, settings).overview(
            workspace_id=context.workspace.workspace.id,
            document_id=document_id,
            workspace_default_currency=context.workspace.workspace.default_currency,
        )
    except (CoordinatePdfError, ValueError) as error:
        raise _conflict(str(error)) from error
    if result is None:
        raise _not_found()
    return result


@router.get(
    "/documents/{document_id}/coordinate-mapping/pages/{page_number}/image",
    responses={
        **api_error_responses(401, 403, 404, 409),
        200: {
            "description": "Bounded PNG rendering of the requested PDF page.",
            "content": {"image/png": {}},
        },
    },
)
async def get_coordinate_mapping_page_image(
    document_id: UUID,
    page_number: int,
    context: Annotated[ApiRequestContext, Depends(require_api_raw_import_read_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    try:
        content = await _service(session, settings).render_page(
            workspace_id=context.workspace.workspace.id,
            document_id=document_id,
            page_number=page_number,
        )
    except (CoordinatePdfError, MappingImportUnavailableError) as error:
        raise _conflict(str(error)) from error
    if content is None:
        raise _not_found()
    return Response(content, media_type="image/png", headers={"Cache-Control": "private, no-store"})


@router.post(
    "/documents/{document_id}/coordinate-mapping/preview",
    response_model=CoordinatePreview,
    responses=api_error_responses(401, 403, 404, 409, 422),
)
async def preview_coordinate_mapping(
    document_id: UUID,
    request: CoordinatePreviewApiRequest,
    context: Annotated[ApiRequestContext, Depends(require_api_raw_import_read_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CoordinatePreview:
    try:
        result = await _service(session, settings).preview(
            workspace_id=context.workspace.workspace.id,
            document_id=document_id,
            spec=request.spec,
        )
    except (CoordinatePdfError, MappingImportUnavailableError) as error:
        raise _conflict(str(error)) from error
    except UnknownStatementMappingError as error:
        raise ApiError(
            status_code=422, code="coordinate_mapping_invalid", message=str(error)
        ) from error
    if result is None:
        raise _not_found()
    return result


@router.post(
    "/documents/{document_id}/coordinate-mapping/import",
    response_model=CoordinateImportApiResponse,
    responses=api_error_responses(401, 403, 404, 409, 422),
)
async def import_coordinate_mapping(
    document_id: UUID,
    request: CoordinateImportApiRequest,
    context: Annotated[ApiRequestContext, Depends(require_api_raw_import_read_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> CoordinateImportApiResponse:
    if not can_manage_imports(context.workspace.membership):
        raise ApiError(
            status_code=403,
            code="import_management_forbidden",
            message="Недостаточно прав для управления импортами.",
        )
    try:
        result = await CoordinateMappingImportService(session, settings).import_rows_idempotently(
            workspace_id=context.workspace.workspace.id,
            document_id=document_id,
            spec=request.spec,
            idempotency_key=idempotency_key,
            template_name=request.template_name,
        )
    except MappingImportNotFoundError as error:
        raise _not_found() from error
    except MappingImportIdempotencyConflictError as error:
        raise ApiError(
            status_code=409, code="coordinate_import_idempotency_conflict", message=str(error)
        ) from error
    except (CoordinatePdfError, MappingImportUnavailableError) as error:
        raise _conflict(str(error)) from error
    except UnknownStatementMappingError as error:
        raise ApiError(
            status_code=422, code="coordinate_mapping_invalid", message=str(error)
        ) from error
    return CoordinateImportApiResponse(
        document_id=result.document_id,
        status=result.document_status,
        imported_row_count=result.imported_row_count,
        template_id=result.template_id,
        replayed=result.replayed,
        review_target=CoordinateImportTargetApiResponse(
            kind="import_review", document_id=result.document_id
        ),
    )


def _not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        code="import_document_not_found",
        message="Документ не найден.",
    )


def _conflict(message: str) -> ApiError:
    return ApiError(
        status_code=status.HTTP_409_CONFLICT, code="coordinate_mapping_unavailable", message=message
    )
