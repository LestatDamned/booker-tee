from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError
from app.api.v1.manual_ledger.mapper import build_manual_ledger_response
from app.api.v1.manual_ledger.query import ManualLedgerQuery, parse_manual_ledger_query
from app.api.v1.manual_ledger.references import ManualLedgerReferenceReader
from app.api.v1.manual_ledger.schemas import ManualLedgerListResponse
from app.db.session import get_session
from app.features.accounts.service import AccountService
from app.features.categories.service import CategoryService
from app.features.ledger.service import LedgerPostingService
from app.features.properties.service import PropertyService
from app.features.workspaces.permissions import permission_flags_for

router = APIRouter(prefix="/manual-ledger", tags=["manual-ledger"])


def get_ledger_posting_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LedgerPostingService:
    return LedgerPostingService(session)


def get_manual_ledger_reference_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ManualLedgerReferenceReader:
    return ManualLedgerReferenceReader(
        accounts=AccountService(session),
        categories=CategoryService(session),
        properties=PropertyService(session),
    )


@router.get("", response_model=ManualLedgerListResponse)
async def list_manual_operations(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    query: Annotated[ManualLedgerQuery, Depends(parse_manual_ledger_query)],
    ledger: Annotated[LedgerPostingService, Depends(get_ledger_posting_service)],
    reference_reader: Annotated[
        ManualLedgerReferenceReader,
        Depends(get_manual_ledger_reference_reader),
    ],
) -> ManualLedgerListResponse:
    if query.date_from and query.date_to and query.date_from > query.date_to:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_date_range",
            message="Начало периода не может быть позже конца периода.",
        )

    operations, page = await ledger.list_manual_operations(
        context.workspace.workspace.id,
        filters=query.filters,
        pagination=query.pagination,
    )
    references = await reference_reader.read(context.workspace.workspace.id)
    can_write = permission_flags_for(context.workspace.membership).can_write_financial_data
    return build_manual_ledger_response(
        operations=operations,
        page=page,
        references=references,
        can_write=can_write,
        target_operation_id=query.operation_id,
    )
