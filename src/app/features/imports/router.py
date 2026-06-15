from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.accounts.service import AccountService
from app.features.categories.service import CategoryService
from app.features.imports.service import (
    ImportDocumentManagementError,
    ImportReparseError,
    ImportService,
    RawTransactionReviewError,
    UploadValidationError,
)
from app.features.ledger.service import LedgerPostingError, LedgerPostingService
from app.features.properties.service import PropertyService
from app.features.transaction_rules.service import TransactionRuleError, TransactionRuleService
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter(prefix="/imports", tags=["imports"])
templates = create_templates()


@router.get("", response_class=HTMLResponse)
async def import_index(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    documents = await ImportService(session, settings).list_documents(context.workspace.id)
    return templates.TemplateResponse(
        request,
        "imports/index.html",
        {
            "app_name": settings.app_name,
            "documents": documents,
            "workspace": context.workspace,
        },
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
    return templates.TemplateResponse(
        request,
        "imports/upload.html",
        {
            "accounts": accounts,
            "app_name": settings.app_name,
            "error": None,
            "workspace": context.workspace,
        },
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
    service = ImportService(session, settings)
    try:
        document = await service.upload_and_extract_statement(
            context=context,
            upload_file=statement_pdf,
            account_id=parsed_account_id,
        )
    except UploadValidationError as exc:
        accounts = await AccountService(session).list_or_create_default(
            context.workspace.id,
            context.workspace.default_currency,
        )
        return templates.TemplateResponse(
            request,
            "imports/upload.html",
            {
                "accounts": accounts,
                "app_name": settings.app_name,
                "error": str(exc),
                "workspace": context.workspace,
            },
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
    document = await ImportService(session, settings).get_document(
        context.workspace.id, document_id
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return templates.TemplateResponse(
        request,
        "imports/detail.html",
        {
            "app_name": settings.app_name,
            "document": document,
            "workspace": context.workspace,
        },
    )


@router.post("/documents/{document_id}/reparse")
async def reparse_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    try:
        await ImportService(session, settings).reparse_document(
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
        await ImportService(session, settings).ignore_document(
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
        await ImportService(session, settings).delete_document(
            workspace_id=context.workspace.id,
            document_id=document_id,
        )
    except ImportDocumentManagementError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return RedirectResponse(url="/imports", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/documents/{document_id}/review", response_class=HTMLResponse)
async def document_review(
    request: Request,
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    document = await ImportService(session, settings).get_document(
        context.workspace.id, document_id
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    accounts = await AccountService(session).list_or_create_default(
        context.workspace.id,
        context.workspace.default_currency,
    )
    categories = await CategoryService(session).list_or_seed_defaults(context.workspace.id)
    properties = await PropertyService(session).list_active(context.workspace.id)
    transfer_suggestions = await LedgerPostingService(
        session
    ).list_transfer_suggestions_for_document(
        workspace_id=context.workspace.id,
        raw_transactions=document.raw_transactions,
    )

    return templates.TemplateResponse(
        request,
        "imports/review.html",
        {
            "accounts": accounts,
            "app_name": settings.app_name,
            "categories": categories,
            "document": document,
            "properties": properties,
            "transfer_suggestions": transfer_suggestions,
            "workspace": context.workspace,
        },
    )


@router.post("/documents/{document_id}/raw-transactions/{raw_transaction_id}/status")
async def update_raw_transaction_status(
    document_id: UUID,
    raw_transaction_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    action: Annotated[str, Form()],
    category_id: Annotated[str | None, Form()] = None,
    counterparty_account_id: Annotated[str | None, Form()] = None,
    matched_raw_transaction_id: Annotated[str | None, Form()] = None,
    property_id: Annotated[str | None, Form()] = None,
    remember_rule: Annotated[str | None, Form()] = None,
    rule_pattern: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        if action == "confirm":
            parsed_category_id = parse_optional_uuid(category_id)
            parsed_property_id = parse_optional_uuid(property_id)
            await LedgerPostingService(session).post_raw_transaction(
                context=context,
                document_id=document_id,
                raw_transaction_id=raw_transaction_id,
                category_id=parsed_category_id,
                property_id=parsed_property_id,
            )
            if remember_rule and parsed_category_id is not None:
                await TransactionRuleService(session).create_rule_from_raw_confirmation(
                    context=context,
                    document_id=document_id,
                    raw_transaction_id=raw_transaction_id,
                    category_id=parsed_category_id,
                    property_id=parsed_property_id,
                    pattern=rule_pattern,
                )
        elif action == "transfer":
            await LedgerPostingService(session).post_raw_transaction_as_transfer(
                context=context,
                document_id=document_id,
                raw_transaction_id=raw_transaction_id,
                counterparty_account_id=parse_optional_uuid(counterparty_account_id),
                matched_raw_transaction_id=parse_optional_uuid(matched_raw_transaction_id),
            )
        else:
            await ImportService(session, settings).set_raw_transaction_review_status(
                workspace_id=context.workspace.id,
                document_id=document_id,
                raw_transaction_id=raw_transaction_id,
                action=action,
            )
    except (ValueError, RawTransactionReviewError, LedgerPostingError, TransactionRuleError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return RedirectResponse(
        url=review_redirect_url(document_id, raw_transaction_id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/documents/{document_id}/raw-transactions/{raw_transaction_id}/undo-posting")
async def undo_raw_transaction_posting(
    document_id: UUID,
    raw_transaction_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    try:
        await LedgerPostingService(session).undo_raw_transaction_posting(
            context=context,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
        )
    except LedgerPostingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return RedirectResponse(
        url=review_redirect_url(document_id, raw_transaction_id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/documents/{document_id}/apply-rules")
async def apply_rules_to_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    try:
        await TransactionRuleService(session).apply_rules_to_document(
            workspace_id=context.workspace.id,
            document_id=document_id,
        )
    except TransactionRuleError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return RedirectResponse(
        url=f"/imports/documents/{document_id}/review",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def review_redirect_url(document_id: UUID, raw_transaction_id: UUID | None = None) -> str:
    url = f"/imports/documents/{document_id}/review"
    if raw_transaction_id is None:
        return url
    return f"{url}#{review_row_anchor(raw_transaction_id)}"


def review_row_anchor(raw_transaction_id: UUID) -> str:
    return f"raw-{raw_transaction_id}"


def parse_optional_uuid(raw_value: str | None) -> UUID | None:
    if not raw_value:
        return None
    return UUID(raw_value)
