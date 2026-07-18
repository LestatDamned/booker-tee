from dataclasses import replace
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
    ManualLedgerFormSubmission,
    business_error_message,
    validate_manual_ledger_create,
)
from app.web.features.ledger.manual.presenter import ManualLedgerPresenter
from app.web.features.ledger.manual.queries import (
    ManualLedgerPageQuery,
    ManualLedgerReferenceQuery,
)
from app.web.features.ledger.manual.query_state import (
    MANUAL_LEDGER_URL,
    ManualLedgerListQuery,
    open_create_url,
    safe_manual_ledger_return_to,
    target_operation_url,
)
from app.web.features.ledger.manual.renderer import ManualLedgerRenderer
from app.web.templating import create_web_templates
from app.web.ui.responses import is_htmx_request

router = APIRouter()
renderer = ManualLedgerRenderer(create_web_templates())


@router.get("/new")
async def manual_ledger_create_panel(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    return_to: Annotated[str | None, Query()] = None,
) -> Response:
    safe_return_to = safe_manual_ledger_return_to(return_to)
    if not is_htmx_request(request):
        return RedirectResponse(
            url=open_create_url(safe_return_to),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    data = await ManualLedgerReferenceQuery(
        accounts=AccountService(session),
        categories=CategoryService(session),
        properties=PropertyService(session),
    ).execute(context=context)
    form = ManualLedgerCreatePresenter().present(
        data=data,
        return_to=safe_return_to,
    )
    return renderer.create_panel(request, form)


@router.post("/new")
async def create_manual_ledger_operation(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
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
    validation = validate_manual_ledger_create(
        ManualLedgerFormSubmission(
            operation_type=operation_type,
            account_id=account_id,
            destination_account_id=destination_account_id,
            amount=amount,
            operation_date=operation_date,
            category_id=category_id,
            property_id=property_id,
            description=description,
        )
    )
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
            form_error = business_error_message(error)

    if not validation.is_valid or form_error is not None:
        data = await ManualLedgerReferenceQuery(
            accounts=AccountService(session),
            categories=CategoryService(session),
            properties=PropertyService(session),
        ).execute(context=context)
        form = ManualLedgerCreatePresenter().present(
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

        list_query = ManualLedgerListQuery.from_return_to(safe_return_to)
        page_data = await ManualLedgerPageQuery(ledger).execute(
            workspace_id=context.workspace.id,
            query=list_query,
        )
        page = ManualLedgerPresenter().present(
            workspace_name=context.workspace.name,
            operations=page_data.operations,
            page=page_data.page,
            filters=list_query.filters,
            focused_operation_id=list_query.focused_operation_id,
            can_write=True,
            references=data,
            create_panel=form,
        )
        return renderer.page(
            request,
            page,
            app_name=settings.app_name,
            response_status=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    if created is None:
        raise RuntimeError("Manual ledger creation produced no result.")
    if not is_htmx_request(request):
        return RedirectResponse(
            url=target_operation_url(safe_return_to, created.id),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    list_query = replace(
        ManualLedgerListQuery.from_return_to(safe_return_to),
        focused_operation_id=created.id,
    )
    page_data = await ManualLedgerPageQuery(ledger).execute(
        workspace_id=context.workspace.id,
        query=list_query,
    )
    presenter = ManualLedgerPresenter()
    page = presenter.present(
        workspace_name=context.workspace.name,
        operations=page_data.operations,
        page=page_data.page,
        filters=list_query.filters,
        focused_operation_id=created.id,
        can_write=True,
        reset_create_panel=True,
        reset_edit_panels=True,
    )
    replace_url = presenter.list_url(
        filters=list_query.filters,
        page=page_data.page.page,
        per_page=page_data.page.per_page,
        focused_operation_id=created.id,
    )
    return renderer.results(
        request,
        page,
        replace_url=replace_url,
        include_create_oob=True,
    )
