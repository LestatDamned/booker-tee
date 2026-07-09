from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.categories.models import CategoryKind
from app.features.categories.service import CategoryError, CategoryService
from app.features.imports.application.documents.status import ImportedDocumentStatusUpdater
from app.features.imports.application.review.actions import (
    RawTransactionReviewUseCase,
)
from app.features.imports.application.review.page_data import ImportReviewPageDataLoader
from app.features.imports.errors import RawTransactionReviewError
from app.features.imports.presentation.review.page import build_review_page_context
from app.features.imports.repository import ImportRepository
from app.features.imports.routes.form_values import RawTransactionReviewFormParser
from app.features.imports.routes.review_responses import (
    ReviewActionResponseRenderer,
    ReviewActionResponseRequest,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.service import LedgerPostingService
from app.features.transaction_rules.application.rule_application import (
    TransactionRuleApplicationUseCase,
)
from app.features.transaction_rules.errors import TransactionRuleError
from app.features.workspaces.dependencies import require_import_management_context
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
    context: Annotated[WorkspaceContext, Depends(require_import_management_context)],
) -> HTMLResponse:
    review_data_loader = ImportReviewPageDataLoader(session)
    document = await review_data_loader.load_document(
        workspace_id=context.workspace.id,
        document_id=document_id,
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    status_updated = await ImportedDocumentStatusUpdater(
        ImportRepository(session)
    ).mark_imported_if_complete(
        workspace_id=context.workspace.id,
        document_id=document_id,
    )
    if status_updated:
        await session.commit()

    page_data = await review_data_loader.load_page_data(
        context=context,
        document=document,
    )
    page_context = build_review_page_context(
        document=document,
        accounts=page_data.accounts,
        categories=page_data.categories,
        properties=page_data.properties,
        transfer_suggestions=page_data.transfer_suggestions,
        existing_transfer_suggestions=page_data.existing_transfer_suggestions,
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
    request: Request,
    document_id: UUID,
    raw_transaction_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_import_management_context)],
    action: Annotated[str, Form()],
    category_id: Annotated[str | None, Form()] = None,
    counterparty_account_id: Annotated[str | None, Form()] = None,
    matched_raw_transaction_id: Annotated[str | None, Form()] = None,
    matched_operation_id: Annotated[str | None, Form()] = None,
    property_id: Annotated[str | None, Form()] = None,
    remember_rule: Annotated[str | None, Form()] = None,
    rule_pattern: Annotated[str | None, Form()] = None,
) -> Response:
    command = RawTransactionReviewFormParser().build_command(
        document_id=document_id,
        raw_transaction_id=raw_transaction_id,
        action=action,
        category_id=category_id,
        property_id=property_id,
        counterparty_account_id=counterparty_account_id,
        matched_raw_transaction_id=matched_raw_transaction_id,
        matched_operation_id=matched_operation_id,
        remember_rule=remember_rule,
        rule_pattern=rule_pattern,
    )
    review_data_loader = ImportReviewPageDataLoader(session)
    response_renderer = ReviewActionResponseRenderer(review_data_loader)
    try:
        result = await RawTransactionReviewUseCase(session, settings).handle(
            context=context,
            command=command,
        )
    except (ValueError, RawTransactionReviewError, LedgerPostingError, TransactionRuleError) as exc:
        if request.headers.get("hx-request") == "true":
            return await response_renderer.render(
                request=request,
                settings=settings,
                context=context,
                response_request=ReviewActionResponseRequest(
                    document_id=document_id,
                    raw_transaction_id=raw_transaction_id,
                    action_error=str(exc),
                    active_panel_type=review_action_panel_type(action),
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return await response_renderer.render(
        request=request,
        settings=settings,
        context=context,
        response_request=ReviewActionResponseRequest(
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
            oob_raw_transaction_ids=result.updated_raw_transaction_ids,
        ),
    )


def review_action_panel_type(action: str) -> str | None:
    if action == "confirm":
        return "category"
    if action == "transfer":
        return "transfer"
    return None


@router.post("/documents/{document_id}/raw-transactions/{raw_transaction_id}/undo-posting")
async def undo_raw_transaction_posting(
    request: Request,
    document_id: UUID,
    raw_transaction_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_import_management_context)],
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

    review_data_loader = ImportReviewPageDataLoader(session)
    response_renderer = ReviewActionResponseRenderer(review_data_loader)
    return await response_renderer.render(
        request=request,
        settings=settings,
        context=context,
        response_request=ReviewActionResponseRequest(
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
        ),
    )


@router.post("/documents/{document_id}/raw-transactions/{raw_transaction_id}/categories")
async def create_review_category(
    request: Request,
    document_id: UUID,
    raw_transaction_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_import_management_context)],
    name: Annotated[str, Form()],
    kind: Annotated[CategoryKind, Form()] = CategoryKind.MIXED,
) -> Response:
    review_data_loader = ImportReviewPageDataLoader(session)
    response_renderer = ReviewActionResponseRenderer(review_data_loader)
    try:
        category = await CategoryService(session).create_custom(
            workspace_id=context.workspace.id,
            name=name,
            kind=kind,
        )
    except CategoryError as exc:
        return await response_renderer.render(
            request=request,
            settings=settings,
            context=context,
            response_request=ReviewActionResponseRequest(
                document_id=document_id,
                raw_transaction_id=raw_transaction_id,
                open_category_editor=True,
                create_category_error=str(exc),
                create_category_initial_name=name,
            ),
        )

    return await response_renderer.render(
        request=request,
        settings=settings,
        context=context,
        response_request=ReviewActionResponseRequest(
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
            selected_category_id=category.id,
            open_category_editor=True,
            refresh_category_options=True,
        ),
    )


@router.post("/documents/{document_id}/apply-rules")
async def apply_rules_to_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_import_management_context)],
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
