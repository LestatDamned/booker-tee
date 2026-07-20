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
    ManualLedgerPageParams,
    ManualLedgerUrlState,
    safe_manual_ledger_return_to,
)
from app.web.features.ledger.manual.renderer import ManualLedgerRenderer
from app.web.features.ledger.manual.response_scope import (
    ManualLedgerUpdateResponseScope,
    ManualLedgerUpdateScope,
)
from app.web.templating import create_web_templates
from app.web.ui.responses import is_htmx_request

router = APIRouter(prefix=MANUAL_LEDGER_URL, tags=["web-manual-ledger"])
router.include_router(create_router)
router.include_router(lifecycle_router)
renderer = ManualLedgerRenderer(create_web_templates())


@router.get("", response_class=HTMLResponse)
async def manual_ledger_page(
    request: Request,
    url_state: Annotated[ManualLedgerUrlState, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_workspace_read_context)],
) -> HTMLResponse:
    page_params = ManualLedgerPageParams.from_url_state(url_state)

    permissions = permission_flags_for(context.membership)
    can_write = permissions.can_write_financial_data

    ledger = LedgerPostingService(session)
    page_data = await ManualLedgerPageQuery(ledger).execute(
        workspace_id=context.workspace.id,
        params=page_params,
    )
    reference_query = ManualLedgerReferenceQuery(
        accounts=AccountService(session),
        categories=CategoryService(session),
        properties=PropertyService(session),
    )
    references = await reference_query.execute(context=context)
    presenter = ManualLedgerPresenter()
    page_vm = presenter.build_page(
        workspace_name=context.workspace.name,
        operations=page_data.operations,
        pagination=page_data.pagination,
        filters=page_params.filters,
        focused_operation_id=url_state.focused_operation_id,
        can_write=can_write,
        references=references,
    )
    return renderer.page(
        request,
        page_vm,
        app_name=settings.app_name,
    )


@router.get("/{operation_id}/edit", response_class=HTMLResponse)
async def manual_ledger_edit_form(
    request: Request,
    operation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    return_to: Annotated[str | None, Query()] = None,
) -> Response:
    safe_return_to = safe_manual_ledger_return_to(return_to)
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

    edit_presenter = ManualLedgerEditPresenter()
    if not is_htmx_request(request):
        form = edit_presenter.build_form(
            data=edit_data,
            return_to=safe_return_to,
        )
        return renderer.form_page(
            request,
            form,
            app_name=settings.app_name,
            workspace_name=context.workspace.name,
            heading="Исправить операцию",
            description="Проверьте данные операции и сохраните изменения.",
            submit_label="Сохранить изменения",
        )

    edit_form = edit_presenter.build_form(data=edit_data, return_to=safe_return_to)
    row = ManualLedgerPresenter().build_row(
        edit_data.operation,
        focused_operation_id=None,
        can_write=True,
        return_to=safe_return_to,
        edit_form=edit_form,
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
    return_state = ManualLedgerUrlState.from_return_to(form_input.return_to)
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
        )
    except LedgerPostingError as error:
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
    response_status = (
        status.HTTP_409_CONFLICT
        if isinstance(error, OperationVersionConflictError)
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )

    if not is_htmx_request(request):
        if isinstance(error, OperationVersionConflictError):
            form = edit_presenter.build_conflict_form(
                data=edit_data,
                return_to=return_to,
                submission=validation.submission,
                message=business_error_message(error),
            )
        else:
            form = edit_presenter.build_form(
                data=edit_data,
                return_to=return_to,
                submission=validation.submission,
                issues=validation.issues,
                form_error=business_error_message(error) if error is not None else None,
            )
        return renderer.form_page(
            request,
            form,
            app_name=app_name,
            workspace_name=context.workspace.name,
            heading="Исправить операцию",
            description="Исправьте отмеченные поля и повторите сохранение.",
            submit_label="Сохранить изменения",
            response_status=response_status,
        )

    if isinstance(error, OperationVersionConflictError):
        edit_form = edit_presenter.build_inline_conflict_form(
            data=edit_data,
            return_to=return_to,
            submission=validation.submission,
            message=business_error_message(error),
        )
    else:
        edit_form = edit_presenter.build_form(
            data=edit_data,
            return_to=return_to,
            submission=validation.submission,
            issues=validation.issues,
            form_error=business_error_message(error) if error is not None else None,
        )
    row = ManualLedgerPresenter().build_row(
        edit_data.operation,
        focused_operation_id=None,
        can_write=True,
        return_to=return_to,
        edit_form=edit_form,
    )
    return renderer.row(
        request,
        row,
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
    return_state: ManualLedgerUrlState,
) -> Response:
    updated_view = await ledger.get_manual_operation(
        workspace_id=context.workspace.id,
        operation_id=updated_operation_id,
    )
    if updated_view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    page_params = ManualLedgerPageParams.from_url_state(return_state)
    update_scope = ManualLedgerUpdateResponseScope().resolve(
        previous=previous_view,
        updated=updated_view,
        filters=page_params.filters,
    )
    if update_scope is ManualLedgerUpdateScope.REPLACE_LIST:
        page_data = await ManualLedgerPageQuery(ledger).execute(
            workspace_id=context.workspace.id,
            params=page_params,
        )
        page_vm = ManualLedgerPresenter().build_page(
            workspace_name=context.workspace.name,
            operations=page_data.operations,
            pagination=page_data.pagination,
            filters=page_params.filters,
            focused_operation_id=return_state.focused_operation_id,
            can_write=True,
            reset_edit_panels=True,
        )
        replace_url = return_state.with_page(page_data.pagination.page).list_url()
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
