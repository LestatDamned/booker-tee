from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.accounts.models import AccountType
from app.features.accounts.service import AccountError, AccountService
from app.features.ledger.service import LedgerPostingService
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter(prefix="/accounts", tags=["accounts"])
templates = create_templates()


@router.get("", response_class=HTMLResponse)
async def account_index(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    account_service = AccountService(session)
    accounts = await account_service.list_accounts(context.workspace.id)
    ledger = LedgerPostingService(session)
    account_details = [
        await ledger.get_account_detail(workspace_id=context.workspace.id, account_id=account.id)
        for account in accounts
    ]
    return templates.TemplateResponse(
        request,
        "accounts/index.html",
        {
            "account_details": [detail for detail in account_details if detail is not None],
            "account_types": list(AccountType),
            "app_name": settings.app_name,
            "workspace": context.workspace,
        },
    )


@router.get("/{account_id}", response_class=HTMLResponse)
async def account_detail(
    request: Request,
    account_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    detail = await LedgerPostingService(session).get_account_detail(
        workspace_id=context.workspace.id,
        account_id=account_id,
    )
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return templates.TemplateResponse(
        request,
        "accounts/detail.html",
        {
            "app_name": settings.app_name,
            "account_types": list(AccountType),
            "detail": detail,
            "workspace": context.workspace,
        },
    )


@router.post("")
async def create_account(
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    name: Annotated[str, Form()],
    account_type: Annotated[AccountType, Form()],
    currency: Annotated[str, Form()],
    initial_balance: Annotated[Decimal, Form()] = Decimal("0.00"),
) -> Response:
    try:
        await AccountService(session).create(
            workspace_id=context.workspace.id,
            name=name,
            account_type=account_type,
            currency=currency,
            initial_balance=initial_balance,
        )
    except (ValueError, AccountError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(url="/accounts", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{account_id}")
async def update_account(
    account_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    name: Annotated[str, Form()],
    account_type: Annotated[AccountType, Form()],
    currency: Annotated[str, Form()],
    initial_balance: Annotated[Decimal, Form()] = Decimal("0.00"),
) -> Response:
    try:
        await AccountService(session).update(
            workspace_id=context.workspace.id,
            account_id=account_id,
            name=name,
            account_type=account_type,
            currency=currency,
            initial_balance=initial_balance,
        )
    except (ValueError, AccountError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(
        url=f"/accounts/{account_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{account_id}/archive")
async def archive_account(
    account_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    await AccountService(session).set_active(
        workspace_id=context.workspace.id,
        account_id=account_id,
        is_active=False,
    )
    return RedirectResponse(url="/accounts", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{account_id}/restore")
async def restore_account(
    account_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    await AccountService(session).set_active(
        workspace_id=context.workspace.id,
        account_id=account_id,
        is_active=True,
    )
    return RedirectResponse(
        url=f"/accounts/{account_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
