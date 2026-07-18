from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.accounts.service import AccountService
from app.features.categories.service import CategoryService
from app.features.ledger.errors import LedgerPostingError, OperationVersionConflictError
from app.features.ledger.service import LedgerPostingService
from app.features.properties.service import PropertyService
from app.features.workspaces.dependencies import (
    require_financial_write_context,
    require_workspace_read_context,
)
from app.features.workspaces.permissions import permission_flags_for
from app.features.workspaces.service import WorkspaceContext
from app.shared.query_params import parse_optional_query_uuid
from app.web.features.ledger.manual.create_presenter import ManualLedgerCreatePresenter
from app.web.features.ledger.manual.create_routes import router as create_router
from app.web.features.ledger.manual.edit_presenter import ManualLedgerEditPresenter
from app.web.features.ledger.manual.forms import (
    ManualLedgerFormSubmission,
    business_error_message,
    validate_manual_ledger_edit,
)
from app.web.features.ledger.manual.lifecycle_routes import router as lifecycle_router
from app.web.features.ledger.manual.presenter import ManualLedgerPresenter
from app.web.features.ledger.manual.queries import (
    ManualLedgerEditQuery,
    ManualLedgerPageQuery,
    ManualLedgerReferenceQuery,
)
from app.web.features.ledger.manual.query_state import (
    MANUAL_LEDGER_URL,
    ManualLedgerListQuery,
    ManualLedgerPageParams,
    open_edit_url,
    safe_manual_ledger_return_to,
    target_operation_url,
)
from app.web.features.ledger.manual.renderer import ManualLedgerRenderer
from app.web.features.ledger.manual.response_scope import (
    ManualLedgerUpdateResponseScope,
    ManualLedgerUpdateScope,
)
from app.web.features.ledger.manual.view_models import ManualLedgerPageVM
from app.web.templating import create_web_templates
from app.web.ui.responses import is_htmx_request

router = APIRouter(prefix=MANUAL_LEDGER_URL, tags=["web-manual-ledger"])
router.include_router(create_router)
router.include_router(lifecycle_router)
renderer = ManualLedgerRenderer(create_web_templates())


@router.get("", response_class=HTMLResponse)
async def manual_ledger_page(
    request: Request,
    params: Annotated[ManualLedgerPageParams, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_workspace_read_context)],
) -> HTMLResponse:
    list_query = ManualLedgerListQuery.from_page_params(params)
    edit_operation_id = parse_optional_query_uuid(params.edit, field_name="edit")
    
    permissions = permission_flags_for(context.membership)
    can_write = permissions.can_write_financial_data
    has_write_intent = params.create or edit_operation_id is not None
    
    if has_write_intent and not can_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для изменения финансовых данных.",
        )

    ledger = LedgerPostingService(session)
    page_data = await ManualLedgerPageQuery(ledger).execute(
        workspace_id=context.workspace.id,
        query=list_query,
    )
    reference_query = ManualLedgerReferenceQuery(
        accounts=AccountService(session),
        categories=CategoryService(session),
        properties=PropertyService(session),
    )
    references = await reference_query.execute(context=context)
    presenter = ManualLedgerPresenter()
    current_url = presenter.list_url(
        filters=list_query.filters,
        page=page_data.page.page,
        per_page=page_data.page.per_page,
        focused_operation_id=list_query.focused_operation_id,
    )

    create_panel = None
    if params.create:
        create_panel = ManualLedgerCreatePresenter().present(
            data=references,
            return_to=current_url,
        )

    edit_panel = None
    if edit_operation_id is not None:
        edit_data = await ManualLedgerEditQuery(
            ledger=ledger,
            references=reference_query,
        ).execute(
            context=context,
            operation_id=edit_operation_id,
            references=references,
        )
        if edit_data is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        edit_panel = ManualLedgerEditPresenter().present(
            data=edit_data,
            return_to=current_url,
        )

    page_vm = presenter.present(
        workspace_name=context.workspace.name,
        operations=page_data.operations,
        page=page_data.page,
        filters=list_query.filters,
        focused_operation_id=list_query.focused_operation_id,
        can_write=can_write,
        references=references,
        create_panel=create_panel,
        edit_panel=edit_panel,
    )
    return renderer.page(
        request,
        page_vm,
        app_name=settings.app_name,
    )


@router.get("/{operation_id}/edit", response_class=HTMLResponse)
async def manual_ledger_edit_panel(
    request: Request,
    operation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    return_to: Annotated[str | None, Query()] = None,
) -> Response:
    safe_return_to = safe_manual_ledger_return_to(return_to)
    if not is_htmx_request(request):
        return RedirectResponse(
            url=open_edit_url(safe_return_to, operation_id),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    ledger = LedgerPostingService(session)
    edit_data = await ManualLedgerEditQuery(
        ledger=ledger,
        references=ManualLedgerReferenceQuery(
            accounts=AccountService(session),
            categories=CategoryService(session),
            properties=PropertyService(session),
        ),
    ).execute(
        context=context,
        operation_id=operation_id,
    )
    if edit_data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    edit_panel = ManualLedgerEditPresenter().present(
        data=edit_data,
        return_to=safe_return_to,
    )
    row = ManualLedgerPresenter().present_row(
        edit_data.operation,
        focused_operation_id=None,
        can_write=True,
        return_to=safe_return_to,
        edit_panel=edit_panel,
    )
    return renderer.edit_panel(request, row)


@router.post("/{operation_id}")
async def update_manual_ledger_operation(
    request: Request,
    operation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    version: Annotated[str, Form()] = "",
    operation_type: Annotated[str, Form()] = "",
    account_id: Annotated[str, Form()] = "",
    destination_account_id: Annotated[str, Form()] = "",
    amount: Annotated[str, Form()] = "",
    operation_date: Annotated[str, Form()] = "",
    category_id: Annotated[str, Form()] = "",
    property_id: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    return_to: Annotated[str, Form()] = MANUAL_LEDGER_URL,
) -> Response:
    safe_return_to = safe_manual_ledger_return_to(return_to)
    validation = validate_manual_ledger_edit(
        operation_id,
        ManualLedgerFormSubmission(
            version=version,
            operation_type=operation_type,
            account_id=account_id,
            destination_account_id=destination_account_id,
            amount=amount,
            operation_date=operation_date,
            category_id=category_id,
            property_id=property_id,
            description=description,
        ),
    )
    ledger = LedgerPostingService(session)
    htmx_request = is_htmx_request(request)
    form_error = None
    conflict_error = None
    previous_operation = None
    updated = None

    if validation.is_valid:
        if htmx_request:
            previous_operation = await ledger.get_manual_operation(
                workspace_id=context.workspace.id,
                operation_id=operation_id,
            )
            if previous_operation is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        command = validation.command
        if command is None:
            raise RuntimeError("Valid manual ledger submission has no command.")
        try:
            updated = await ledger.update_manual_operation(
                context=context,
                command=command,
            )
        except OperationVersionConflictError as error:
            # The use case rolls the failed transaction back. SQLAlchemy expires
            # ORM-backed workspace context objects on rollback, so reload the
            # workspace asynchronously before rebuilding the local 409 response.
            await session.refresh(context.workspace)
            conflict_error = business_error_message(error)
        except LedgerPostingError as error:
            form_error = business_error_message(error)

    if not validation.is_valid or form_error is not None or conflict_error is not None:
        edit_data = await ManualLedgerEditQuery(
            ledger=ledger,
            references=ManualLedgerReferenceQuery(
                accounts=AccountService(session),
                categories=CategoryService(session),
                properties=PropertyService(session),
            ),
        ).execute(
            context=context,
            operation_id=operation_id,
        )
        if edit_data is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        edit_presenter = ManualLedgerEditPresenter()
        edit_panel = (
            edit_presenter.present_conflict(
                data=edit_data,
                return_to=safe_return_to,
                submission=validation.submission,
                message=conflict_error,
            )
            if conflict_error is not None
            else edit_presenter.present(
                data=edit_data,
                return_to=safe_return_to,
                submission=validation.submission,
                issues=validation.issues,
                form_error=form_error,
            )
        )
        response_status = (
            status.HTTP_409_CONFLICT
            if conflict_error is not None
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        presenter = ManualLedgerPresenter()
        if htmx_request:
            row = presenter.present_row(
                edit_data.operation,
                focused_operation_id=None,
                can_write=True,
                return_to=safe_return_to,
                edit_panel=edit_panel,
            )
            return renderer.row(
                request,
                row,
                response_status=response_status,
            )

        list_query = ManualLedgerListQuery.from_return_to(safe_return_to)
        page_data = await ManualLedgerPageQuery(ledger).execute(
            workspace_id=context.workspace.id,
            query=list_query,
        )
        page_vm: ManualLedgerPageVM = presenter.present(
            workspace_name=context.workspace.name,
            operations=page_data.operations,
            page=page_data.page,
            filters=list_query.filters,
            focused_operation_id=list_query.focused_operation_id,
            can_write=True,
            references=edit_data.references,
            edit_panel=edit_panel,
        )
        return renderer.page(
            request,
            page_vm,
            app_name=settings.app_name,
            response_status=response_status,
        )

    if updated is None:
        raise RuntimeError("Manual ledger update produced no result.")
    if not htmx_request:
        return RedirectResponse(
            url=target_operation_url(safe_return_to, updated.id),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    operation = await ledger.get_manual_operation(
        workspace_id=context.workspace.id,
        operation_id=updated.id,
    )
    if operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if previous_operation is None:
        raise RuntimeError("HTMX manual ledger update has no previous operation state.")

    list_query = ManualLedgerListQuery.from_return_to(safe_return_to)
    response_scope = ManualLedgerUpdateResponseScope().resolve(
        previous=previous_operation,
        updated=operation,
        filters=list_query.filters,
    )
    if response_scope is ManualLedgerUpdateScope.REPLACE_LIST:
        page_data = await ManualLedgerPageQuery(ledger).execute(
            workspace_id=context.workspace.id,
            query=list_query,
        )
        page_vm = ManualLedgerPresenter().present(
            workspace_name=context.workspace.name,
            operations=page_data.operations,
            page=page_data.page,
            filters=list_query.filters,
            focused_operation_id=list_query.focused_operation_id,
            can_write=True,
            reset_edit_panels=True,
        )
        replace_url = ManualLedgerPresenter().list_url(
            filters=list_query.filters,
            page=page_data.page.page,
            per_page=page_data.page.per_page,
            focused_operation_id=list_query.focused_operation_id,
        )
        return renderer.results(
            request,
            page_vm,
            replace_url=replace_url,
        )

    row = ManualLedgerPresenter().present_row(
        operation,
        focused_operation_id=None,
        can_write=True,
        return_to=safe_return_to,
        reset_edit_panel=True,
    )
    return renderer.row(request, row)
