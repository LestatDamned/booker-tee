from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError, api_error_responses
from app.api.v1.imports.dependencies import get_import_document_list_reader
from app.api.v1.imports.list_parameters import (
    ImportDocumentListParameters,
    parse_import_document_list_parameters,
)
from app.api.v1.imports.mapping import ImportDocumentListResponseMapper
from app.api.v1.imports.schemas import ImportDocumentListApiResponse
from app.features.imports.application.documents.listing import ImportDocumentListReader
from app.features.workspaces.permissions import permission_flags_for

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
