from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.accounts.presentation.detail.models import AccountDetailPresenterInput
from app.features.accounts.presentation.detail.presenter import AccountDetailPresenter
from app.features.categories.service import CategoryService
from app.features.ledger.application.account_ledger import (
    AccountLedgerEntryView,
    AccountLedgerReader,
)
from app.features.ledger.application.imported_operations import (
    ImportedOperationReviewUseCase,
    UpdateImportedOperationReviewFieldsCommand,
)
from app.features.ledger.domain.types import imported_operation_actions
from app.features.ledger.errors import (
    ImportedOperationNotEditableError,
    ImportedOperationNotFoundError,
    OperationVersionConflictError,
)
from app.features.ledger.models import OperationSource
from app.features.ledger.schemas.listing import (
    AccountEntryFilters,
    LedgerPage,
)
from app.features.properties.service import PropertyService
from app.features.workspaces.dependencies import (
    require_financial_write_context,
)
from app.features.workspaces.service import WorkspaceContext
from app.shared.query_params import (
    parse_optional_query_uuid,
)
from app.templating import create_templates

router = APIRouter(prefix="/accounts", tags=["accounts"])
templates = create_templates()


@router.get("/{account_id}", response_class=HTMLResponse)
async def account_detail(
    request: Request,
    account_id: UUID,
) -> RedirectResponse:
    query = request.url.query
    target = f"/app/accounts/{account_id}"
    return RedirectResponse(
        url=f"{target}?{query}" if query else target,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
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
    if not imported_operation_actions(operation.status).can_edit_review_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only confirmed imported operations can be edited.",
        )
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
    version: Annotated[int, Form()],
    description: Annotated[str | None, Form()] = None,
    category_id: Annotated[str | None, Form()] = None,
    property_id: Annotated[str | None, Form()] = None,
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
                expected_version=version,
                category_id=parse_optional_query_uuid(category_id, field_name="category_id"),
                property_id=parse_optional_query_uuid(property_id, field_name="property_id"),
                description=description,
            ),
        )
    except ImportedOperationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ImportedOperationNotEditableError, OperationVersionConflictError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
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
