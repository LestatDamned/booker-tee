from decimal import Decimal
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.accounts.models import AccountType
from app.features.accounts.presentation.detail.models import AccountDetailPresenterInput
from app.features.accounts.presentation.detail.presenter import AccountDetailPresenter
from app.features.accounts.service import AccountError, AccountService
from app.features.categories.service import CategoryService
from app.features.ledger.application.account_ledger import (
    AccountLedgerEntryView,
    AccountLedgerReader,
)
from app.features.ledger.application.imported_operations import (
    ImportedOperationReviewUseCase,
    UpdateImportedOperationReviewFieldsCommand,
)
from app.features.ledger.application.listing import (
    AccountEntryFilters,
    LedgerPage,
    normalize_pagination,
)
from app.features.ledger.models import OperationSource, OperationStatus, OperationType
from app.features.properties.service import PropertyService
from app.features.workspaces.dependencies import (
    get_current_workspace_context,
    require_financial_write_context,
)
from app.features.workspaces.permissions import permission_flags_for
from app.features.workspaces.service import WorkspaceContext
from app.shared.query_params import (
    clean_optional_query_text,
    parse_optional_query_date,
    parse_optional_query_enum,
    parse_optional_query_uuid,
)
from app.templating import create_templates

router = APIRouter(prefix="/accounts", tags=["accounts"])
templates = create_templates()


@router.get("", response_class=HTMLResponse)
async def account_index(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    account_service = AccountService(session)
    accounts = await account_service.list_accounts(context.workspace.id)
    ledger = AccountLedgerReader(session)
    account_details = [
        await ledger.get_detail(workspace_id=context.workspace.id, account_id=account.id)
        for account in accounts
    ]
    return templates.TemplateResponse(
        request,
        "accounts/index.html",
        {
            "account_details": [detail for detail in account_details if detail is not None],
            "account_types": list(AccountType),
            "app_name": settings.app_name,
            "workspace": context.workspace,
        },
    )


@router.get("/{account_id}", response_class=HTMLResponse)
async def account_detail(
    request: Request,
    account_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
    source: Annotated[str | None, Query()] = None,
    operation_type_filter: Annotated[str | None, Query(alias="type")] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    category_id: Annotated[str | None, Query()] = None,
    property_id: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=200)] = 50,
) -> HTMLResponse:
    filters = AccountEntryFilters(
        date_from=parse_optional_query_date(date_from, field_name="date_from"),
        date_to=parse_optional_query_date(date_to, field_name="date_to"),
        source=parse_optional_query_enum(source, OperationSource, field_name="source"),
        operation_type=parse_optional_query_enum(
            operation_type_filter,
            OperationType,
            field_name="type",
        ),
        status=parse_optional_query_enum(status_filter, OperationStatus, field_name="status")
        or OperationStatus.CONFIRMED,
        category_id=parse_optional_query_uuid(category_id, field_name="category_id"),
        property_id=parse_optional_query_uuid(property_id, field_name="property_id"),
        search=clean_optional_query_text(search),
    )
    detail = await AccountLedgerReader(session).get_detail(
        workspace_id=context.workspace.id,
        account_id=account_id,
        filters=filters,
        pagination=normalize_pagination(page, per_page),
    )
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    categories = await CategoryService(session).list_or_seed_defaults(
        context.workspace.id,
        context.workspace.type,
        include_inactive=True,
    )
    properties = await PropertyService(session).list_all(context.workspace.id)
    account_page = AccountDetailPresenter.build(
        detail,
        AccountDetailPresenterInput(
            can_write=permission_flags_for(context.membership).can_write_financial_data,
            filters_date_from=filters.date_from,
            filters_date_to=filters.date_to,
            filters_source=filters.source,
            filters_operation_type=filters.operation_type,
            filters_status=filters.status,
            filters_category_id=filters.category_id,
            filters_property_id=filters.property_id,
            filters_search=filters.search,
        ),
    )

    return templates.TemplateResponse(
        request,
        "accounts/detail.html",
        {
            "account_page": account_page,
            "app_name": settings.app_name,
            "account_types": list(AccountType),
            "categories": categories,
            "detail": detail,
            "filters": filters,
            "operation_sources": list(OperationSource),
            "operation_statuses": list(OperationStatus),
            "operation_types": list(OperationType),
            "page_urls": account_detail_page_urls(account_id, filters, detail.page),
            "properties": properties,
            "workspace": context.workspace,
        },
    )


@router.post("")
async def create_account(
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    name: Annotated[str, Form()],
    account_type: Annotated[AccountType, Form()],
    currency: Annotated[str, Form()],
    initial_balance: Annotated[Decimal, Form()] = Decimal("0.00"),
) -> Response:
    try:
        await AccountService(session).create(
            workspace_id=context.workspace.id,
            name=name,
            account_type=account_type,
            currency=currency,
            initial_balance=initial_balance,
        )
    except (ValueError, AccountError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(url="/accounts", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{account_id}")
async def update_account(
    account_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    name: Annotated[str, Form()],
    account_type: Annotated[AccountType, Form()],
    currency: Annotated[str, Form()],
    initial_balance: Annotated[Decimal, Form()] = Decimal("0.00"),
) -> Response:
    try:
        await AccountService(session).update(
            workspace_id=context.workspace.id,
            account_id=account_id,
            name=name,
            account_type=account_type,
            currency=currency,
            initial_balance=initial_balance,
        )
    except (ValueError, AccountError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(
        url=f"/accounts/{account_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{account_id}/archive")
async def archive_account(
    account_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> Response:
    await AccountService(session).set_active(
        workspace_id=context.workspace.id,
        account_id=account_id,
        is_active=False,
    )
    return RedirectResponse(url="/accounts", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{account_id}/restore")
async def restore_account(
    account_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> Response:
    await AccountService(session).set_active(
        workspace_id=context.workspace.id,
        account_id=account_id,
        is_active=True,
    )
    return RedirectResponse(
        url=f"/accounts/{account_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/{account_id}/operations/{operation_id}/review-fields/edit",
    response_class=HTMLResponse,
)
async def imported_operation_review_fields_panel(
    request: Request,
    account_id: UUID,
    operation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> HTMLResponse:
    operation = await AccountLedgerReader(session).get_imported_operation(
        workspace_id=context.workspace.id,
        operation_id=operation_id,
        account_id=account_id,
    )
    if operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    categories = await CategoryService(session).list_or_seed_defaults(
        context.workspace.id,
        context.workspace.type,
        include_inactive=True,
    )
    properties = await PropertyService(session).list_all(context.workspace.id)
    edit_panel = AccountDetailPresenter.build_edit_panel(
        account_id=account_id,
        operation=operation,
    )
    return templates.TemplateResponse(
        request,
        "accounts/detail/_movement_edit_panel.html",
        {
            "categories": categories,
            "edit_panel": edit_panel,
            "operation_statuses": list(OperationStatus),
            "properties": properties,
        },
    )


@router.post("/{account_id}/operations/{operation_id}/review-fields")
async def update_imported_operation_review_fields(
    request: Request,
    account_id: UUID,
    operation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    description: Annotated[str | None, Form()] = None,
    category_id: Annotated[str | None, Form()] = None,
    property_id: Annotated[str | None, Form()] = None,
    operation_status: Annotated[OperationStatus, Form(alias="status")] = (
        OperationStatus.CONFIRMED
    ),
) -> Response:
    account_operation = await AccountLedgerReader(session).get_imported_operation(
        workspace_id=context.workspace.id,
        operation_id=operation_id,
        account_id=account_id,
    )
    if account_operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        operation = await ImportedOperationReviewUseCase(session).update_review_fields(
            context=context,
            command=UpdateImportedOperationReviewFieldsCommand(
                operation_id=operation_id,
                category_id=parse_optional_query_uuid(category_id, field_name="category_id"),
                property_id=parse_optional_query_uuid(property_id, field_name="property_id"),
                description=description,
                status=operation_status,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if is_htmx(request):
        return await account_movement_row_response(
            request=request,
            session=session,
            context=context,
            account_id=account_id,
            operation_id=operation.id,
        )
    redirect_filters = AccountEntryFilters(
        source=OperationSource.BANK_PDF,
        status=operation.status,
    )
    return RedirectResponse(
        url=f"{account_detail_url(account_id, redirect_filters, page=1, per_page=50)}"
        f"#operation-{operation_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


async def account_movement_row_response(
    *,
    request: Request,
    session: AsyncSession,
    context: WorkspaceContext,
    account_id: UUID,
    operation_id: UUID,
) -> HTMLResponse:
    operation = await AccountLedgerReader(session).get_imported_operation(
        workspace_id=context.workspace.id,
        operation_id=operation_id,
        account_id=account_id,
    )
    if operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    money_entry = next(
        (entry for entry in operation.money_entries if entry.account_id == account_id),
        None,
    )
    if money_entry is None or money_entry.account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    movement = AccountDetailPresenter.build_movement(
        money_entry.account,
        AccountLedgerEntryView(
            operation=operation,
            operation_id=operation.id,
            amount=money_entry.amount,
            currency=money_entry.account.currency,
        ),
        AccountDetailPresenterInput(
            can_write=True,
            filters_date_from=None,
            filters_date_to=None,
            filters_source=None,
            filters_operation_type=None,
            filters_status=None,
            filters_category_id=None,
            filters_property_id=None,
            filters_search=None,
        ),
    )
    return templates.TemplateResponse(
        request,
        "accounts/detail/_movement.html",
        {
            "movement": movement,
        },
    )


def account_detail_page_urls(
    account_id: UUID,
    filters: AccountEntryFilters,
    page: LedgerPage,
) -> dict[str, str | None]:
    return {
        "previous": account_detail_url(
            account_id,
            filters,
            page=page.previous_page,
            per_page=page.per_page,
        )
        if page.has_previous
        else None,
        "next": account_detail_url(
            account_id,
            filters,
            page=page.next_page,
            per_page=page.per_page,
        )
        if page.has_next
        else None,
    }


def account_detail_url(
    account_id: UUID,
    filters: AccountEntryFilters,
    *,
    page: int,
    per_page: int,
) -> str:
    params = {
        "date_from": filters.date_from.isoformat() if filters.date_from else None,
        "date_to": filters.date_to.isoformat() if filters.date_to else None,
        "source": filters.source.value if filters.source else None,
        "type": filters.operation_type.value if filters.operation_type else None,
        "status": filters.status.value if filters.status else None,
        "category_id": str(filters.category_id) if filters.category_id else None,
        "property_id": str(filters.property_id) if filters.property_id else None,
        "search": filters.search,
        "page": page,
        "per_page": per_page,
    }
    query = urlencode({key: value for key, value in params.items() if value not in {None, ""}})
    return f"/accounts/{account_id}?{query}"


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"
