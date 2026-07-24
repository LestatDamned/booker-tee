from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.accounts.service import AccountService
from app.features.imports.application.documents.upload import StatementUploadUseCase
from app.features.imports.errors import UploadValidationError
from app.features.imports.presentation.documents import (
    UploadPageContext,
)
from app.features.workspaces.dependencies import (
    require_import_management_context,
)
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter()
templates = create_templates()


@router.get("/upload", response_class=HTMLResponse)
async def upload_form(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_import_management_context)],
) -> HTMLResponse:
    accounts = await AccountService(session).list_active_accounts(context.workspace.id)
    page_context = UploadPageContext(accounts=accounts)
    return templates.TemplateResponse(
        request,
        "imports/upload.html",
        page_context.template_values(
            app_name=settings.app_name,
            workspace=context.workspace,
        ),
    )


@router.post("/upload")
async def upload_statement(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_import_management_context)],
    statement_pdf: Annotated[UploadFile, File()],
    account_id: Annotated[UUID, Form()],
) -> Response:
    try:
        document = await StatementUploadUseCase(
            session,
            settings,
        ).upload_and_extract_statement(
            context=context,
            upload_file=statement_pdf,
            account_id=account_id,
        )
    except UploadValidationError as exc:
        accounts = await AccountService(session).list_active_accounts(context.workspace.id)
        page_context = UploadPageContext(accounts=accounts, error=str(exc))
        return templates.TemplateResponse(
            request,
            "imports/upload.html",
            page_context.template_values(
                app_name=settings.app_name,
                workspace=context.workspace,
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=f"/app/imports/documents/{document.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/documents/{document_id}")
async def document_detail(
    request: Request,
    document_id: UUID,
) -> Response:
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(
        url=f"/app/imports/documents/{document_id}{query}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
