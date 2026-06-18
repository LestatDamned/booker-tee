from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.accounts.service import AccountService
from app.features.imports.application.documents.management import (
    ImportDocumentManagementUseCase,
)
from app.features.imports.application.documents.reparse import StatementReparseUseCase
from app.features.imports.application.documents.upload import StatementUploadUseCase
from app.features.imports.errors import (
    ImportDocumentManagementError,
    ImportReparseError,
    UploadValidationError,
)
from app.features.imports.presentation.documents import (
    DocumentDetailPageContext,
    ImportIndexPageContext,
    UploadPageContext,
)
from app.features.imports.service import ImportService
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter()
templates = create_templates()


@router.get("", response_class=HTMLResponse)
async def import_index(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    documents = await ImportService(session).list_documents(context.workspace.id)
    page_context = ImportIndexPageContext(documents=documents)
    return templates.TemplateResponse(
        request,
        "imports/index.html",
        page_context.template_values(
            app_name=settings.app_name,
            workspace=context.workspace,
        ),
    )


@router.get("/upload", response_class=HTMLResponse)
async def upload_form(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    accounts = await AccountService(session).list_or_create_default(
        context.workspace.id,
        context.workspace.default_currency,
    )
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
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    statement_pdf: Annotated[UploadFile, File()],
    account_id: Annotated[str | None, Form()] = None,
) -> Response:
    parsed_account_id = UUID(account_id) if account_id else None
    try:
        document = await StatementUploadUseCase(
            session,
            settings,
        ).upload_and_extract_statement(
            context=context,
            upload_file=statement_pdf,
            account_id=parsed_account_id,
        )
    except UploadValidationError as exc:
        accounts = await AccountService(session).list_or_create_default(
            context.workspace.id,
            context.workspace.default_currency,
        )
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
        url=f"/imports/documents/{document.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/documents/{document_id}", response_class=HTMLResponse)
async def document_detail(
    request: Request,
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    view = await ImportService(session).get_document_detail_view(context.workspace.id, document_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    page_context = DocumentDetailPageContext(view=view)
    return templates.TemplateResponse(
        request,
        "imports/detail.html",
        page_context.template_values(
            app_name=settings.app_name,
            workspace=context.workspace,
        ),
    )


@router.post("/documents/{document_id}/reparse")
async def reparse_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    try:
        await StatementReparseUseCase(session, settings).reparse_document(
            context=context,
            document_id=document_id,
        )
    except ImportReparseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return RedirectResponse(
        url=f"/imports/documents/{document_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/documents/{document_id}/ignore")
async def ignore_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    try:
        await ImportDocumentManagementUseCase(session, settings).ignore_document(
            workspace_id=context.workspace.id,
            document_id=document_id,
        )
    except ImportDocumentManagementError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return RedirectResponse(url="/imports", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/documents/{document_id}/delete")
async def delete_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    try:
        await ImportDocumentManagementUseCase(session, settings).delete_document(
            workspace_id=context.workspace.id,
            document_id=document_id,
        )
    except ImportDocumentManagementError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return RedirectResponse(url="/imports", status_code=status.HTTP_303_SEE_OTHER)
