from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.accounts.service import AccountService
from app.features.categories.service import CategoryService
from app.features.imports.application.review.actions import (
    RawTransactionReviewCommand,
    RawTransactionReviewUseCase,
)
from app.features.imports.errors import RawTransactionReviewError
from app.features.imports.presentation.review import (
    build_review_page_context,
    review_redirect_url,
)
from app.features.imports.routes.form_values import parse_optional_uuid
from app.features.imports.service import ImportService
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.service import LedgerPostingService
from app.features.properties.service import PropertyService
from app.features.transaction_rules.application.rule_application import (
    TransactionRuleApplicationUseCase,
)
from app.features.transaction_rules.errors import TransactionRuleError
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter()
templates = create_templates()


@router.get("/documents/{document_id}/review", response_class=HTMLResponse)
async def document_review(
    request: Request,
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    document = await ImportService(session).get_document(context.workspace.id, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    accounts = await AccountService(session).list_or_create_default(
        context.workspace.id,
        context.workspace.default_currency,
    )
    categories = await CategoryService(session).list_or_seed_defaults(
        context.workspace.id,
        context.workspace.type,
    )
    properties = await PropertyService(session).list_active(context.workspace.id)
    transfer_suggestions = await LedgerPostingService(
        session
    ).list_transfer_suggestions_for_document(
        workspace_id=context.workspace.id,
        raw_transactions=document.raw_transactions,
    )
    page_context = build_review_page_context(
        document=document,
        accounts=accounts,
        categories=categories,
        properties=properties,
        transfer_suggestions=transfer_suggestions,
    )

    return templates.TemplateResponse(
        request,
        "imports/review.html",
        page_context.template_values(
            app_name=settings.app_name,
            workspace=context.workspace,
        ),
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
    command = RawTransactionReviewCommand(
        document_id=document_id,
        raw_transaction_id=raw_transaction_id,
        action=action,
        category_id=parse_optional_uuid(category_id),
        property_id=parse_optional_uuid(property_id),
        counterparty_account_id=parse_optional_uuid(counterparty_account_id),
        matched_raw_transaction_id=parse_optional_uuid(matched_raw_transaction_id),
        remember_rule=remember_rule is not None,
        rule_pattern=rule_pattern,
    )
    try:
        await RawTransactionReviewUseCase(session, settings).handle(
            context=context,
            command=command,
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
        await TransactionRuleApplicationUseCase(session).apply_rules_to_document(
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
