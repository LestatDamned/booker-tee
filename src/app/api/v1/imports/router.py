from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError, api_error_responses
from app.api.v1.imports.dependencies import (
    get_import_document_detail_reader,
    get_import_document_list_reader,
)
from app.api.v1.imports.list_parameters import (
    ImportDocumentListParameters,
    parse_import_document_list_parameters,
)
from app.api.v1.imports.mapping import (
    ImportDocumentDetailResponseMapper,
    ImportDocumentListResponseMapper,
)
from app.api.v1.imports.schemas import (
    ImportDocumentDeleteApiResponse,
    ImportDocumentDetailApiResponse,
    ImportDocumentListApiResponse,
    ImportDocumentMutationApiRequest,
)
from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.imports.application.documents.detail_reading import (
    ImportDocumentDetailReader,
)
from app.features.imports.application.documents.listing import ImportDocumentListReader
from app.features.imports.application.documents.management import (
    ImportDocumentManagementUseCase,
)
from app.features.imports.application.documents.reparse import StatementReparseUseCase
from app.features.imports.errors import ImportDocumentManagementError, ImportReparseError
from app.features.imports.service import ImportService
from app.features.workspaces.permissions import can_manage_imports, permission_flags_for

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get(
    "/documents",
    response_model=ImportDocumentListApiResponse,
    responses=api_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ),
)
async def list_import_documents(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    parameters: Annotated[
        ImportDocumentListParameters,
        Depends(parse_import_document_list_parameters),
    ],
    reader: Annotated[
        ImportDocumentListReader,
        Depends(get_import_document_list_reader),
    ],
) -> ImportDocumentListApiResponse:
    if (
        parameters.period_from is not None
        and parameters.period_to is not None
        and parameters.period_from > parameters.period_to
    ):
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_period_range",
            message="Начало периода не может быть позже конца периода.",
        )
    permissions = permission_flags_for(context.workspace.membership)
    documents = await reader.read(
        workspace_id=context.workspace.workspace.id,
        workspace_name=context.workspace.workspace.name,
        can_upload=permissions.can_manage_imports,
        filters=parameters.filters,
        pagination=parameters.pagination,
    )
    return ImportDocumentListResponseMapper.response(documents)


@router.get(
    "/documents/{document_id}",
    response_model=ImportDocumentDetailApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
)
async def get_import_document(
    document_id: UUID,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    reader: Annotated[
        ImportDocumentDetailReader,
        Depends(get_import_document_detail_reader),
    ],
) -> ImportDocumentDetailApiResponse:
    detail = await reader.read(
        workspace_id=context.workspace.workspace.id,
        document_id=document_id,
        can_manage=can_manage_imports(context.workspace.membership),
    )
    if detail is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="import_document_not_found",
            message="Документ не найден.",
        )
    return ImportDocumentDetailResponseMapper.response(detail)


@router.post(
    "/documents/{document_id}/reparse",
    response_model=ImportDocumentDetailApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
    ),
)
async def reparse_import_document(
    document_id: UUID,
    request: ImportDocumentMutationApiRequest,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportDocumentDetailApiResponse:
    _require_import_management(context)
    try:
        await StatementReparseUseCase(session, settings).reparse_document(
            context=context.workspace,
            document_id=document_id,
            expected_status=request.expected_status,
        )
    except ImportReparseError as error:
        raise _mutation_error(error) from error
    return await _read_committed_detail(
        session=session,
        workspace_id=context.workspace.workspace.id,
        document_id=document_id,
    )


@router.post(
    "/documents/{document_id}/ignore",
    response_model=ImportDocumentDetailApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
    ),
)
async def ignore_import_document(
    document_id: UUID,
    request: ImportDocumentMutationApiRequest,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportDocumentDetailApiResponse:
    _require_import_management(context)
    try:
        await ImportDocumentManagementUseCase(session, settings).ignore_document(
            workspace_id=context.workspace.workspace.id,
            document_id=document_id,
            expected_status=request.expected_status,
        )
    except ImportDocumentManagementError as error:
        raise _mutation_error(error) from error
    return await _read_committed_detail(
        session=session,
        workspace_id=context.workspace.workspace.id,
        document_id=document_id,
    )


@router.delete(
    "/documents/{document_id}",
    response_model=ImportDocumentDeleteApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
    ),
)
async def delete_import_document(
    document_id: UUID,
    request: ImportDocumentMutationApiRequest,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportDocumentDeleteApiResponse:
    _require_import_management(context)
    try:
        await ImportDocumentManagementUseCase(session, settings).delete_document(
            workspace_id=context.workspace.workspace.id,
            document_id=document_id,
            expected_status=request.expected_status,
        )
    except ImportDocumentManagementError as error:
        raise _mutation_error(error) from error
    return ImportDocumentDeleteApiResponse(
        id=document_id,
        deleted=True,
        navigation_target="document_list",
    )


async def _read_committed_detail(
    *,
    session: AsyncSession,
    workspace_id: UUID,
    document_id: UUID,
) -> ImportDocumentDetailApiResponse:
    view = await ImportService(session).get_document_detail_view(workspace_id, document_id)
    if view is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="import_document_not_found",
            message="Документ не найден.",
        )
    detail = ImportDocumentDetailReader.from_view(view, can_manage=True)
    return ImportDocumentDetailResponseMapper.response(detail)


def _require_import_management(context: ApiRequestContext) -> None:
    if not can_manage_imports(context.workspace.membership):
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="import_management_forbidden",
            message="Недостаточно прав для управления импортами.",
        )


def _mutation_error(error: Exception) -> ApiError:
    message = str(error)
    not_found = "not found" in message.lower() or "не найден" in message.lower()
    return ApiError(
        status_code=(status.HTTP_404_NOT_FOUND if not_found else status.HTTP_409_CONFLICT),
        code="import_document_not_found" if not_found else "import_document_conflict",
        message="Документ не найден." if not_found else message,
    )
