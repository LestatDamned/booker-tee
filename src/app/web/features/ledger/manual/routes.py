from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.ledger.application.listing import ManualOperationFilters, normalize_pagination
from app.features.ledger.models import OperationStatus, OperationType
from app.features.ledger.service import LedgerPostingService
from app.features.workspaces.dependencies import require_workspace_read_context
from app.features.workspaces.permissions import permission_flags_for
from app.features.workspaces.service import WorkspaceContext
from app.shared.query_params import (
    clean_optional_query_text,
    parse_optional_query_date,
    parse_optional_query_enum,
    parse_optional_query_uuid,
)
from app.web.features.ledger.manual.presenter import ManualLedgerPresenter
from app.web.templating import create_web_templates

router = APIRouter(prefix="/_next/ledger/manual", tags=["web-manual-ledger"])
templates = create_web_templates()


@router.get("", response_class=HTMLResponse)
async def manual_ledger_page(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_workspace_read_context)],
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
    operation_type_filter: Annotated[str | None, Query(alias="type")] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query()] = None,
    operation_id: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=200)] = 50,
) -> HTMLResponse:
    filters = ManualOperationFilters(
        date_from=parse_optional_query_date(date_from, field_name="date_from"),
        date_to=parse_optional_query_date(date_to, field_name="date_to"),
        operation_type=parse_optional_query_enum(
            operation_type_filter,
            OperationType,
            field_name="type",
        ),
        status=parse_optional_query_enum(status_filter, OperationStatus, field_name="status"),
        search=clean_optional_query_text(search),
    )
    focused_operation_id = parse_optional_query_uuid(operation_id, field_name="operation_id")
    operations, ledger_page = await LedgerPostingService(session).list_manual_operations(
        context.workspace.id,
        filters=filters,
        pagination=normalize_pagination(page, per_page),
    )
    page_vm = ManualLedgerPresenter().present(
        workspace_name=context.workspace.name,
        operations=operations,
        page=ledger_page,
        filters=filters,
        focused_operation_id=focused_operation_id,
        can_write=permission_flags_for(context.membership).can_write_financial_data,
    )
    return templates.TemplateResponse(
        request,
        "features/ledger/manual/index.html",
        {
            "app_name": settings.app_name,
            "page_title": "Ручные операции",
            "page": page_vm,
        },
    )
