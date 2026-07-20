from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.accounts.service import AccountService
from app.features.categories.service import CategoryService
from app.features.ledger.application.commands import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.service import LedgerPostingService
from app.features.properties.service import PropertyService
from app.features.workspaces.dependencies import require_financial_write_context
from app.features.workspaces.service import WorkspaceContext
from app.web.features.ledger.manual.create_presenter import ManualLedgerCreatePresenter
from app.web.features.ledger.manual.forms import (
    ManualLedgerCreateValidation,
    ManualLedgerFormInput,
    business_error_message,
)
from app.web.features.ledger.manual.presenter import ManualLedgerPresenter
from app.web.features.ledger.manual.queries import (
    ManualLedgerPageQuery,
    ManualLedgerReferenceQuery,
)
from app.web.features.ledger.manual.query_state import (
    ManualLedgerPageParams,
    ManualLedgerUrlState,
    safe_manual_ledger_return_to,
)
from app.web.features.ledger.manual.renderer import ManualLedgerRenderer
from app.web.templating import create_web_templates
from app.web.ui.responses import is_htmx_request

router = APIRouter()
renderer = ManualLedgerRenderer(create_web_templates())


@router.get("/new")
async def manual_ledger_create_form(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    return_to: Annotated[str | None, Query()] = None,
) -> Response:
    safe_return_to = safe_manual_ledger_return_to(return_to)
    data = await ManualLedgerReferenceQuery(
        accounts=AccountService(session),
        categories=CategoryService(session),
        properties=PropertyService(session),
    ).execute(context=context)
    form = ManualLedgerCreatePresenter().build_form(
        data=data,
        return_to=safe_return_to,
    )
    if is_htmx_request(request):
        return renderer.create_panel(request, form)
    return renderer.form_page(
        request,
        form,
        app_name=settings.app_name,
        workspace_name=context.workspace.name,
        heading="Добавить ручную операцию",
        description="Создайте доход, расход или перевод между своими счетами.",
        submit_label="Создать операцию",
    )


@router.post("/new")
async def create_manual_ledger_operation(
    request: Request,
    form_input: Annotated[ManualLedgerFormInput, Form()],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> Response:
    safe_return_to = safe_manual_ledger_return_to(form_input.return_to)
    validation = ManualLedgerCreateValidation.from_form_input(form_input=form_input)
    ledger = LedgerPostingService(session)
    form_error = None
    created = None

    if validation.is_valid:
        command = validation.command
        if command is None:
            raise RuntimeError("Valid manual ledger creation has no command.")
        try:
            if isinstance(command, CreateManualTransferCommand):
                created = await ledger.create_manual_transfer(
                    context=context,
                    command=command,
                )
            elif isinstance(command, CreateManualIncomeExpenseCommand):
                created = await ledger.create_manual_income_expense(
                    context=context,
                    command=command,
                )
        except LedgerPostingError as error:
            await session.refresh(context.workspace)
            form_error = business_error_message(error)

    if not validation.is_valid or form_error is not None:
        data = await ManualLedgerReferenceQuery(
            accounts=AccountService(session),
            categories=CategoryService(session),
            properties=PropertyService(session),
        ).execute(context=context)
        form = ManualLedgerCreatePresenter().build_form(
            data=data,
            return_to=safe_return_to,
            submission=validation.submission,
            issues=validation.issues,
            form_error=form_error,
        )
        if is_htmx_request(request):
            return renderer.create_panel(
                request,
                form,
                response_status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )

        return renderer.form_page(
            request,
            form,
            app_name=settings.app_name,
            workspace_name=context.workspace.name,
            heading="Добавить ручную операцию",
            description="Исправьте отмеченные поля и повторите сохранение.",
            submit_label="Создать операцию",
            response_status=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    if created is None:
        raise RuntimeError("Manual ledger creation produced no result.")
    if not is_htmx_request(request):
        return RedirectResponse(
            url=ManualLedgerUrlState.from_return_to(safe_return_to).target_operation_url(
                created.id
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    url_state = ManualLedgerUrlState.from_return_to(safe_return_to).model_copy(
        update={"operation_id": created.id}
    )
    page_params = ManualLedgerPageParams.from_url_state(url_state)
    page_data = await ManualLedgerPageQuery(ledger).execute(
        workspace_id=context.workspace.id,
        params=page_params,
    )
    presenter = ManualLedgerPresenter()
    page = presenter.build_page(
        workspace_name=context.workspace.name,
        operations=page_data.operations,
        pagination=page_data.pagination,
        filters=page_params.filters,
        focused_operation_id=created.id,
        can_write=True,
        reset_create_panel=True,
        reset_edit_panels=True,
    )
    replace_url = url_state.with_page(page_data.pagination.page).list_url()
    return renderer.results(
        request,
        page,
        replace_url=replace_url,
        include_create_oob=True,
    )
