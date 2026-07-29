from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError, api_error_responses
from app.api.v1.imports.dependencies import (
    get_unknown_statement_mapping_importer,
    get_unknown_statement_mapping_reader,
)
from app.api.v1.imports.mapping_response import (
    UnknownStatementMappingResponseMapper,
)
from app.api.v1.imports.mapping_schemas import (
    MappingControlTotalCellApiModel,
    MappingImportApiRequest,
    MappingImportApiResponse,
    MappingImportTargetApiResponse,
    MappingPreviewApiRequest,
    MappingPreviewApiResponse,
    MappingReadApiResponse,
    MappingSourceRowsApiResponse,
)
from app.features.imports.application.unknown_statement_mappings.import_use_case import (
    UnknownStatementMappingImportUseCase,
)
from app.features.imports.application.unknown_statement_mappings.reader import (
    MappingUnavailableError,
    UnknownStatementMappingReader,
)
from app.features.imports.mapping.dto import (
    MappingControlTotalCellRef,
    StatementMappingSpec,
)
from app.features.imports.mapping.errors import (
    MappingImportIdempotencyConflictError,
    MappingImportNotFoundError,
    MappingImportUnavailableError,
    UnknownStatementMappingError,
)
from app.features.imports.mapping.validation import (
    MappingCommandValidationError,
)
from app.features.workspaces.permissions import can_manage_imports

router = APIRouter()


@router.get(
    "/documents/{document_id}/mapping",
    response_model=MappingReadApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
)
async def get_unknown_statement_mapping(
    document_id: UUID,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    reader: Annotated[
        UnknownStatementMappingReader,
        Depends(get_unknown_statement_mapping_reader),
    ],
) -> MappingReadApiResponse:
    _require_import_management(context)
    mapping = await reader.read(
        workspace_id=context.workspace.workspace.id,
        document_id=document_id,
        workspace_default_currency=context.workspace.workspace.default_currency,
    )
    if mapping is None:
        raise _not_found()
    return UnknownStatementMappingResponseMapper.read(mapping)


@router.get(
    "/documents/{document_id}/mapping/tables/{page_number}/{table_index}/rows",
    response_model=MappingSourceRowsApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
)
async def get_unknown_statement_mapping_source_rows(
    document_id: UUID,
    page_number: int,
    table_index: int,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    reader: Annotated[
        UnknownStatementMappingReader,
        Depends(get_unknown_statement_mapping_reader),
    ],
    start_row_number: Annotated[int, Query(ge=1, alias="startRowNumber")] = 1,
    row_limit: Annotated[int, Query(ge=1, le=50, alias="rowLimit")] = 30,
) -> MappingSourceRowsApiResponse:
    _require_import_management(context)
    rows = await reader.source_rows(
        workspace_id=context.workspace.workspace.id,
        document_id=document_id,
        page_number=page_number,
        table_index=table_index,
        start_row_number=start_row_number,
        row_limit=row_limit,
    )
    if rows is None:
        raise _not_found()
    return UnknownStatementMappingResponseMapper.source_rows(rows)


@router.post(
    "/documents/{document_id}/mapping/preview",
    response_model=MappingPreviewApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def preview_unknown_statement_mapping(
    document_id: UUID,
    request: MappingPreviewApiRequest,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    reader: Annotated[
        UnknownStatementMappingReader,
        Depends(get_unknown_statement_mapping_reader),
    ],
) -> MappingPreviewApiResponse:
    _require_import_management(context)
    try:
        preview = await reader.preview(
            workspace_id=context.workspace.workspace.id,
            document_id=document_id,
            workspace_default_currency=context.workspace.workspace.default_currency,
            spec=_mapping_spec(request),
        )
    except MappingCommandValidationError as error:
        raise _mapping_validation_api_error(error) from error
    except MappingUnavailableError as error:
        reason = error.reason_codes[0]
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=f"mapping_{reason.value}",
            message=str(error),
        ) from error
    if preview is None:
        raise _not_found()
    return UnknownStatementMappingResponseMapper.preview(preview)


@router.post(
    "/documents/{document_id}/mapping/import",
    response_model=MappingImportApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def import_unknown_statement_mapping(
    document_id: UUID,
    request: MappingImportApiRequest,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    importer: Annotated[
        UnknownStatementMappingImportUseCase,
        Depends(get_unknown_statement_mapping_importer),
    ],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> MappingImportApiResponse:
    _require_import_management(context)
    try:
        result = await importer.import_mapped_rows_idempotently(
            workspace_id=context.workspace.workspace.id,
            document_id=document_id,
            spec=_mapping_spec(request),
            idempotency_key=idempotency_key,
            template_name=request.template_name,
        )
    except MappingCommandValidationError as error:
        raise _mapping_validation_api_error(error) from error
    except MappingImportNotFoundError as error:
        raise _not_found() from error
    except MappingImportIdempotencyConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="mapping_import_idempotency_conflict",
            message=str(error),
        ) from error
    except MappingImportUnavailableError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="mapping_import_unavailable",
            message=str(error),
        ) from error
    except UnknownStatementMappingError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="mapping_import_invalid",
            message=str(error),
        ) from error

    return MappingImportApiResponse(
        document_id=result.document.id,
        status=result.document.status,
        imported_row_count=result.imported_row_count,
        template_id=result.template_id,
        replayed=result.replayed,
        review_target=MappingImportTargetApiResponse(
            kind="import_review",
            document_id=result.document.id,
        ),
    )


def _mapping_validation_api_error(error: MappingCommandValidationError) -> ApiError:
    field_errors: dict[str, list[str]] = {}
    for issue in error.issues:
        for field in issue.fields:
            field_errors.setdefault(field, []).append(issue.message)
    return ApiError(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="mapping_validation_failed",
        message="Исправьте ошибки в настройке колонок.",
        field_errors=field_errors,
    )


def _mapping_spec(
    request: MappingPreviewApiRequest | MappingImportApiRequest,
) -> StatementMappingSpec:
    mapping = request.mapping
    return StatementMappingSpec(
        page_number=mapping.table_ref.page_number,
        table_index=mapping.table_ref.table_index,
        operation_date_column=mapping.operation_date_column,
        posting_date_column=mapping.posting_date_column,
        description_column=mapping.description_column,
        amount_column=mapping.amount_column,
        debit_amount_column=mapping.debit_amount_column,
        credit_amount_column=mapping.credit_amount_column,
        currency_column=mapping.currency_column,
        balance_after_column=mapping.balance_after_column,
        first_data_row=mapping.first_data_row_number - 1,
        default_currency=mapping.default_currency,
        unsigned_amount_direction=mapping.unsigned_amount_direction,
        opening_balance_cell=_control_total_cell(mapping.opening_balance_cell),
        closing_balance_cell=_control_total_cell(mapping.closing_balance_cell),
    )


def _control_total_cell(
    value: MappingControlTotalCellApiModel | None,
) -> MappingControlTotalCellRef | None:
    if value is None:
        return None
    return MappingControlTotalCellRef(
        page_number=value.table_ref.page_number,
        table_index=value.table_ref.table_index,
        row_number=value.row_number - 1,
        column_index=value.column_index,
    )


def _require_import_management(context: ApiRequestContext) -> None:
    if not can_manage_imports(context.workspace.membership):
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="import_management_forbidden",
            message="Недостаточно прав для управления импортами.",
        )


def _not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        code="import_document_not_found",
        message="Документ не найден.",
    )
