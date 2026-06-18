from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.imports.application.unknown_statement_mappings.form_commands import (
    command_from_form_data,
)
from app.features.imports.application.unknown_statement_mappings.import_use_case import (
    UnknownStatementMappingImportUseCase,
)
from app.features.imports.application.unknown_statement_mappings.template_use_case import (
    UnknownStatementMappingTemplateUseCase,
)
from app.features.imports.errors import UnknownStatementMappingError
from app.features.imports.presentation.mapping import (
    build_mapping_page_context,
    parse_table_ref,
    preview_mapping_page_context,
)
from app.features.imports.service import ImportService
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter()
templates = create_templates()


@router.get("/documents/{document_id}/mapping", response_class=HTMLResponse)
async def document_mapping_form(
    request: Request,
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    view = await ImportService(session).get_document_detail_view(context.workspace.id, document_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    mapping_templates = await UnknownStatementMappingTemplateUseCase(
        session
    ).list_matching_templates(
        workspace_id=context.workspace.id,
        bank_name=view.bank_name,
        statement_type=view.statement_type,
    )
    page_context = build_mapping_page_context(
        view=view,
        default_currency=view.account.currency
        if view.account
        else context.workspace.default_currency,
        mapping_templates=mapping_templates,
    )
    return templates.TemplateResponse(
        request,
        "imports/mapping.html",
        page_context.template_values(
            app_name=settings.app_name,
            view=view,
            workspace=context.workspace,
        ),
    )


@router.post("/documents/{document_id}/mapping", response_class=HTMLResponse)
async def preview_document_mapping(
    request: Request,
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    table_ref: Annotated[str, Form()],
    operation_date_column: Annotated[int, Form()],
    description_column: Annotated[int, Form()],
    amount_column: Annotated[int, Form()],
    posting_date_column: Annotated[int, Form()] = -1,
    debit_amount_column: Annotated[int, Form()] = -1,
    credit_amount_column: Annotated[int, Form()] = -1,
    balance_after_column: Annotated[int, Form()] = -1,
    currency_column: Annotated[int, Form()] = -1,
    first_data_row: Annotated[int, Form()] = 1,
    default_currency: Annotated[str, Form()] = "RUB",
) -> HTMLResponse:
    view = await ImportService(session).get_document_detail_view(context.workspace.id, document_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    page_number, table_index = parse_table_ref(table_ref)
    command = command_from_form_data(
        page_number=page_number,
        table_index=table_index,
        operation_date_column=operation_date_column,
        posting_date_column=posting_date_column,
        description_column=description_column,
        amount_column=amount_column,
        currency_column=currency_column,
        first_data_row=first_data_row,
        default_currency=default_currency,
        debit_amount_column=debit_amount_column,
        credit_amount_column=credit_amount_column,
        balance_after_column=balance_after_column,
    )
    mapping_templates = await UnknownStatementMappingTemplateUseCase(
        session
    ).list_matching_templates(
        workspace_id=context.workspace.id,
        bank_name=view.bank_name,
        statement_type=view.statement_type,
    )
    page_context = preview_mapping_page_context(
        view=view,
        command=command,
        mapping_templates=mapping_templates,
    )
    return templates.TemplateResponse(
        request,
        "imports/mapping.html",
        page_context.template_values(
            app_name=settings.app_name,
            view=view,
            workspace=context.workspace,
        ),
    )


@router.post("/documents/{document_id}/mapping/import")
async def import_document_mapping(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    table_ref: Annotated[str, Form()],
    operation_date_column: Annotated[int, Form()],
    description_column: Annotated[int, Form()],
    amount_column: Annotated[int, Form()],
    posting_date_column: Annotated[int, Form()] = -1,
    debit_amount_column: Annotated[int, Form()] = -1,
    credit_amount_column: Annotated[int, Form()] = -1,
    balance_after_column: Annotated[int, Form()] = -1,
    currency_column: Annotated[int, Form()] = -1,
    first_data_row: Annotated[int, Form()] = 1,
    default_currency: Annotated[str, Form()] = "RUB",
    save_template_name: Annotated[str | None, Form()] = None,
) -> Response:
    page_number, table_index = parse_table_ref(table_ref)
    command = command_from_form_data(
        page_number=page_number,
        table_index=table_index,
        operation_date_column=operation_date_column,
        posting_date_column=posting_date_column,
        description_column=description_column,
        amount_column=amount_column,
        currency_column=currency_column,
        first_data_row=first_data_row,
        default_currency=default_currency,
        debit_amount_column=debit_amount_column,
        credit_amount_column=credit_amount_column,
        balance_after_column=balance_after_column,
    )
    try:
        await UnknownStatementMappingImportUseCase(session).import_mapped_rows(
            workspace_id=context.workspace.id,
            document_id=document_id,
            command=command,
            template_name=save_template_name,
        )
    except UnknownStatementMappingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return RedirectResponse(
        url=f"/imports/documents/{document_id}/review",
        status_code=status.HTTP_303_SEE_OTHER,
    )
