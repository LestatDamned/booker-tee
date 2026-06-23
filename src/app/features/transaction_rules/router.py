from decimal import Decimal
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
from app.features.ledger.models import OperationType
from app.features.properties.service import PropertyService
from app.features.transaction_rules.application.fixture_seeding import DefaultMerchantRuleSeeder
from app.features.transaction_rules.application.rule_management import (
    TransactionRuleManagementUseCase,
)
from app.features.transaction_rules.application.rule_queries import TransactionRuleQueryUseCase
from app.features.transaction_rules.errors import TransactionRuleError
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.features.transaction_rules.router_forms import (
    build_create_rule_command,
    build_update_rule_command,
)
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter(prefix="/rules", tags=["transaction-rules"])
templates = create_templates()


@router.get("", response_class=HTMLResponse)
async def rules_index(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    accounts = await AccountService(session).list_active_accounts(context.workspace.id)
    categories = await CategoryService(session).list_or_seed_defaults(
        context.workspace.id,
        context.workspace.type,
    )
    properties = await PropertyService(session).list_active(context.workspace.id)
    rules = await TransactionRuleQueryUseCase(session).list_rules(context.workspace.id)
    return templates.TemplateResponse(
        request,
        "transaction_rules/index.html",
        {
            "accounts": accounts,
            "application_modes": list(TransactionRuleApplicationMode),
            "app_name": settings.app_name,
            "categories": categories,
            "directions": list(MoneyDirection),
            "match_types": list(TransactionRuleMatchType),
            "operation_types": list(OperationType),
            "properties": properties,
            "rules": rules,
            "workspace": context.workspace,
        },
    )


@router.post("")
async def create_rule(
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    pattern: Annotated[str, Form()],
    match_type: Annotated[TransactionRuleMatchType, Form()],
    direction: Annotated[MoneyDirection, Form()],
    application_mode: Annotated[TransactionRuleApplicationMode, Form()],
    name: Annotated[str | None, Form()] = None,
    category_id: Annotated[str | None, Form()] = None,
    property_id: Annotated[str | None, Form()] = None,
    target_operation_type: Annotated[str | None, Form()] = None,
    amount_min: Annotated[Decimal | None, Form()] = None,
    amount_max: Annotated[Decimal | None, Form()] = None,
) -> Response:
    try:
        rule = await TransactionRuleManagementUseCase(session).create_rule(
            context=context,
            command=build_create_rule_command(
                name=name,
                pattern=pattern,
                match_type=match_type,
                category_id=category_id,
                property_id=property_id,
                target_operation_type=target_operation_type,
                direction=direction,
                application_mode=application_mode,
                amount_min=amount_min,
                amount_max=amount_max,
            ),
        )
    except (ValueError, TransactionRuleError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(url=rule_anchor_url(rule.id), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/seed-defaults")
async def seed_default_rules(
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    await DefaultMerchantRuleSeeder(session).seed(context)
    return RedirectResponse(url="/rules", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{rule_id}")
async def update_rule(
    rule_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    pattern: Annotated[str, Form()],
    match_type: Annotated[TransactionRuleMatchType, Form()],
    direction: Annotated[MoneyDirection, Form()],
    application_mode: Annotated[TransactionRuleApplicationMode, Form()],
    name: Annotated[str | None, Form()] = None,
    category_id: Annotated[str | None, Form()] = None,
    property_id: Annotated[str | None, Form()] = None,
    target_operation_type: Annotated[str | None, Form()] = None,
    amount_min: Annotated[Decimal | None, Form()] = None,
    amount_max: Annotated[Decimal | None, Form()] = None,
) -> Response:
    try:
        rule = await TransactionRuleManagementUseCase(session).update_rule(
            context=context,
            command=build_update_rule_command(
                rule_id=rule_id,
                name=name,
                pattern=pattern,
                match_type=match_type,
                category_id=category_id,
                property_id=property_id,
                target_operation_type=target_operation_type,
                direction=direction,
                application_mode=application_mode,
                amount_min=amount_min,
                amount_max=amount_max,
            ),
        )
    except (ValueError, TransactionRuleError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(url=rule_anchor_url(rule.id), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{rule_id}/toggle")
async def toggle_rule(
    rule_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    is_active: Annotated[bool, Form()] = False,
) -> Response:
    rule = await TransactionRuleManagementUseCase(session).set_rule_active(
        workspace_id=context.workspace.id,
        rule_id=rule_id,
        is_active=is_active,
    )
    return RedirectResponse(url=rule_anchor_url(rule.id), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{rule_id}/delete")
async def delete_rule(
    rule_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    await TransactionRuleManagementUseCase(session).delete_rule(
        workspace_id=context.workspace.id,
        rule_id=rule_id,
    )
    return RedirectResponse(url="/rules", status_code=status.HTTP_303_SEE_OTHER)


def rule_anchor_url(rule_id: UUID) -> str:
    return f"/rules#rule-{rule_id}"
