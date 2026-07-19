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
from app.features.ledger.mapping.dto import ManualOperationView
from app.features.ledger.service import LedgerPostingService
from app.features.properties.service import PropertyService
from app.features.workspaces.dependencies import (
    require_financial_write_context,
    require_workspace_read_context,
)
from app.features.workspaces.permissions import permission_flags_for
from app.features.workspaces.service import WorkspaceContext
from app.web.features.ledger.manual.create_presenter import ManualLedgerCreatePresenter
from app.web.features.ledger.manual.create_routes import router as create_router
from app.web.features.ledger.manual.edit_presenter import ManualLedgerEditPresenter
from app.web.features.ledger.manual.forms import (
    ManualLedgerEditValidation,
    ManualLedgerFormInput,
    business_error_message,
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
    safe_manual_ledger_return_to,
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
    edit_operation_id = params.edit

    permissions = permission_flags_for(context.membership)
    can_write = permissions.can_write_financial_data
    has_write_intent = params.create_requested or edit_operation_id is not None

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
    current_url = ManualLedgerPageParams.from_list_state(
        filters=list_query.filters,
        page=page_data.page.page,
        per_page=page_data.page.per_page,
        focused_operation_id=list_query.focused_operation_id,
    ).list_url()

    create_panel = None
    if params.create_requested:
        create_panel = ManualLedgerCreatePresenter().build_form(
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
        edit_panel = ManualLedgerEditPresenter().build_panel(
            data=edit_data,
            return_to=current_url,
        )

    page_vm = presenter.build_page(
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
            url=ManualLedgerPageParams.from_return_to(safe_return_to).open_edit_url(operation_id),
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

    edit_panel = ManualLedgerEditPresenter().build_panel(
        data=edit_data,
        return_to=safe_return_to,
    )
    row = ManualLedgerPresenter().build_row(
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
    form_input: Annotated[ManualLedgerFormInput, Form()],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> Response:
    safe_return_to = safe_manual_ledger_return_to(form_input.return_to)
    return_state = ManualLedgerPageParams.from_return_to(safe_return_to)
    validation = ManualLedgerEditValidation.from_form_input(
        operation_id=operation_id,
        form_input=form_input,
    )
    ledger = LedgerPostingService(session)
    is_htmx = is_htmx_request(request)
    if not validation.is_valid:
        return await _render_manual_ledger_update_failure(
            request,
            operation_id=operation_id,
            validation=validation,
            error=None,
            ledger=ledger,
            session=session,
            context=context,
            app_name=settings.app_name,
            return_to=safe_return_to,
            return_state=return_state,
        )

    previous_view = None
    if is_htmx:
        previous_view = await ledger.get_manual_operation(
            workspace_id=context.workspace.id,
            operation_id=operation_id,
        )
        if previous_view is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    command = validation.command
    if command is None:
        raise RuntimeError("Valid manual ledger submission has no command.")

    try:
        updated_record = await ledger.update_manual_operation(
            context=context,
            command=command,
        )
    except OperationVersionConflictError as error:
        # The use case rolls the failed transaction back. SQLAlchemy expires
        # ORM-backed workspace context objects on rollback, so reload the
        # workspace asynchronously before rebuilding the local 409 response.
        await session.refresh(context.workspace)
        return await _render_manual_ledger_update_failure(
            request,
            operation_id=operation_id,
            validation=validation,
            error=error,
            ledger=ledger,
            session=session,
            context=context,
            app_name=settings.app_name,
            return_to=safe_return_to,
            return_state=return_state,
        )
    except LedgerPostingError as error:
        return await _render_manual_ledger_update_failure(
            request,
            operation_id=operation_id,
            validation=validation,
            error=error,
            ledger=ledger,
            session=session,
            context=context,
            app_name=settings.app_name,
            return_to=safe_return_to,
            return_state=return_state,
        )

    if not is_htmx:
        return RedirectResponse(
            url=return_state.target_operation_url(updated_record.id),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if previous_view is None:
        raise RuntimeError("HTMX manual ledger update has no previous operation state.")
    return await _render_manual_ledger_htmx_update_success(
        request,
        updated_operation_id=updated_record.id,
        previous_view=previous_view,
        ledger=ledger,
        context=context,
        return_to=safe_return_to,
        return_state=return_state,
    )


async def _render_manual_ledger_update_failure(
    request: Request,
    *,
    operation_id: UUID,
    validation: ManualLedgerEditValidation,
    error: LedgerPostingError | None,
    ledger: LedgerPostingService,
    session: AsyncSession,
    context: WorkspaceContext,
    app_name: str,
    return_to: str,
    return_state: ManualLedgerPageParams,
) -> Response:
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
    if isinstance(error, OperationVersionConflictError):
        edit_panel = edit_presenter.build_conflict_panel(
            data=edit_data,
            return_to=return_to,
            submission=validation.submission,
            message=business_error_message(error),
        )
        response_status = status.HTTP_409_CONFLICT
    else:
        edit_panel = edit_presenter.build_panel(
            data=edit_data,
            return_to=return_to,
            submission=validation.submission,
            issues=validation.issues,
            form_error=business_error_message(error) if error is not None else None,
        )
        response_status = status.HTTP_422_UNPROCESSABLE_CONTENT

    presenter = ManualLedgerPresenter()
    if is_htmx_request(request):
        row = presenter.build_row(
            edit_data.operation,
            focused_operation_id=None,
            can_write=True,
            return_to=return_to,
            edit_panel=edit_panel,
        )
        return renderer.row(
            request,
            row,
            response_status=response_status,
        )

    list_query = ManualLedgerListQuery.from_page_params(return_state)
    page_data = await ManualLedgerPageQuery(ledger).execute(
        workspace_id=context.workspace.id,
        query=list_query,
    )
    page_vm: ManualLedgerPageVM = presenter.build_page(
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
        app_name=app_name,
        response_status=response_status,
    )


async def _render_manual_ledger_htmx_update_success(
    request: Request,
    *,
    updated_operation_id: UUID,
    previous_view: ManualOperationView,
    ledger: LedgerPostingService,
    context: WorkspaceContext,
    return_to: str,
    return_state: ManualLedgerPageParams,
) -> Response:
    updated_view = await ledger.get_manual_operation(
        workspace_id=context.workspace.id,
        operation_id=updated_operation_id,
    )
    if updated_view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    list_query = ManualLedgerListQuery.from_page_params(return_state)
    update_scope = ManualLedgerUpdateResponseScope().resolve(
        previous=previous_view,
        updated=updated_view,
        filters=list_query.filters,
    )
    if update_scope is ManualLedgerUpdateScope.REPLACE_LIST:
        page_data = await ManualLedgerPageQuery(ledger).execute(
            workspace_id=context.workspace.id,
            query=list_query,
        )
        page_vm = ManualLedgerPresenter().build_page(
            workspace_name=context.workspace.name,
            operations=page_data.operations,
            page=page_data.page,
            filters=list_query.filters,
            focused_operation_id=list_query.focused_operation_id,
            can_write=True,
            reset_edit_panels=True,
        )
        replace_url = ManualLedgerPageParams.from_list_state(
            filters=list_query.filters,
            page=page_data.page.page,
            per_page=page_data.page.per_page,
            focused_operation_id=list_query.focused_operation_id,
        ).list_url()
        return renderer.results(
            request,
            page_vm,
            replace_url=replace_url,
        )

    row = ManualLedgerPresenter().build_row(
        updated_view,
        focused_operation_id=None,
        can_write=True,
        return_to=return_to,
        reset_edit_panel=True,
    )
    return renderer.row(request, row)
