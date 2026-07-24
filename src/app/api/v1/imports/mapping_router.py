from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError, api_error_responses
from app.api.v1.imports.dependencies import get_unknown_statement_mapping_reader
from app.api.v1.imports.mapping_response import (
    UnknownStatementMappingResponseMapper,
)
from app.api.v1.imports.mapping_schemas import (
    MappingPreviewApiRequest,
    MappingPreviewApiResponse,
    MappingReadApiResponse,
)
from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappingCommand,
)
from app.features.imports.application.unknown_statement_mappings.reader import (
    MappingCommandValidationError,
    MappingUnavailableError,
    UnknownStatementMappingReader,
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
            command=_mapping_command(request),
        )
    except MappingCommandValidationError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=error.code,
            message=error.message,
            field_errors={field: [error.message] for field in error.fields},
        ) from error
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


def _mapping_command(request: MappingPreviewApiRequest) -> UnknownStatementMappingCommand:
    mapping = request.mapping
    return UnknownStatementMappingCommand(
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
