from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status
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
from app.api.v1.imports.mapping_router import router as mapping_router
from app.api.v1.imports.schemas import (
    ImportDocumentDeleteApiResponse,
    ImportDocumentDetailApiResponse,
    ImportDocumentListApiResponse,
    ImportDocumentMutationApiRequest,
    ImportDocumentUploadApiResponse,
    ImportUploadReferenceAccountApiResponse,
    ImportUploadReferenceApiResponse,
)
from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.accounts.service import AccountService
from app.features.imports.application.documents.management import (
    ImportDocumentManagementUseCase,
)
from app.features.imports.application.documents.upload import StatementUploadUseCase
from app.features.imports.documents.queries.detail import (
    ImportDocumentDetailReader,
)
from app.features.imports.documents.queries.list import ImportDocumentListReader
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.errors import (
    ImportDocumentManagementError,
    UploadAccountNotFoundError,
    UploadIdempotencyConflictError,
    UploadTooLargeError,
    UploadValidationError,
)
from app.features.workspaces.permissions import can_manage_imports, permission_flags_for

router = APIRouter(prefix="/imports", tags=["imports"])
router.include_router(mapping_router)


@router.get(
    "/upload-reference",
    response_model=ImportUploadReferenceApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ),
)
async def get_import_upload_reference(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportUploadReferenceApiResponse:
    accounts = await AccountService(session).list_active_accounts(context.workspace.workspace.id)
    return ImportUploadReferenceApiResponse(
        accounts=[
            ImportUploadReferenceAccountApiResponse(
                id=account.id,
                name=account.name,
                currency=account.currency,
                bank_name=account.bank_name,
            )
            for account in accounts
        ],
        accepted_extensions=[".pdf", ".xlsx"],
        accepted_content_types=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ],
        max_file_size_bytes=settings.statement_upload_max_bytes,
        can_upload=can_manage_imports(context.workspace.membership),
    )


@router.post(
    "/documents",
    response_model=ImportDocumentUploadApiResponse,
    status_code=status.HTTP_201_CREATED,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_413_CONTENT_TOO_LARGE,
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def upload_import_document(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    statement: Annotated[UploadFile, File()],
    account_id: Annotated[UUID, Form()],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> ImportDocumentUploadApiResponse:
    _require_import_management(context)
    try:
        result = await StatementUploadUseCase(session, settings).upload_statement(
            context=context.workspace,
            upload_file=statement,
            account_id=account_id,
            idempotency_key=idempotency_key,
        )
    except UploadAccountNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="upload_account_not_found",
            message=str(error),
            field_errors={"accountId": [str(error)]},
        ) from error
    except UploadIdempotencyConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="upload_idempotency_conflict",
            message=str(error),
        ) from error
    except UploadTooLargeError as error:
        raise ApiError(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            code="upload_too_large",
            message=str(error),
            field_errors={"statement": [str(error)]},
        ) from error
    except UploadValidationError as error:
        raise ApiError(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            code="unsupported_statement_type",
            message=str(error),
            field_errors={"statement": [str(error)]},
        ) from error

    detail = await _read_committed_detail(
        session=session,
        workspace_id=context.workspace.workspace.id,
        document_id=result.document.id,
    )
    return ImportDocumentUploadApiResponse(
        id=result.document.id,
        status=result.document.status,
        replayed=result.replayed,
        navigation_target="document_detail",
        next_step=detail.next_step,
    )


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
    detail = await ImportDocumentDetailReader(DocumentRepository(session)).read(
        workspace_id=workspace_id,
        document_id=document_id,
        can_manage=True,
    )
    if detail is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="import_document_not_found",
            message="Документ не найден.",
        )
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
