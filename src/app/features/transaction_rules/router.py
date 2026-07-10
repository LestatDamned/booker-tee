from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.categories.service import CategoryService
from app.features.properties.service import PropertyService
from app.features.transaction_rules.application.fixture_seeding import DefaultMerchantRuleSeeder
from app.features.transaction_rules.application.rule_management import (
    TransactionRuleManagementUseCase,
)
from app.features.transaction_rules.application.rule_queries import (
    TransactionRuleQueryUseCase,
)
from app.features.transaction_rules.errors import TransactionRuleError
from app.features.transaction_rules.listing import RULE_LIST_DEFAULT_LIMIT, normalize_limit
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.features.transaction_rules.presentation.models import RulesPageVM
from app.features.transaction_rules.presentation.presenter import TransactionRulesPagePresenter
from app.features.transaction_rules.router_forms import (
    build_create_rule_command,
    build_update_rule_command,
)
from app.features.workspaces.dependencies import (
    get_current_workspace_context,
    require_financial_write_context,
)
from app.features.workspaces.permissions import permission_flags_for
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
    q: Annotated[str | None, Query()] = None,
    category_id: Annotated[str | None, Query()] = None,
    rule_status: Annotated[str, Query(alias="status")] = "all",
    limit: Annotated[int, Query()] = RULE_LIST_DEFAULT_LIMIT,
) -> HTMLResponse:
    page = await build_rules_page(
        session=session,
        context=context,
        can_write=permission_flags_for(context.membership).can_write_financial_data,
        filter_search=q or "",
        filter_category_id=parse_optional_filter_uuid(category_id),
        filter_status=rule_status,
        limit=limit,
    )
    return templates.TemplateResponse(
        request,
        "transaction_rules/index.html",
        {
            "app_name": settings.app_name,
            "page": page,
            "workspace": context.workspace,
        },
    )


@router.post("")
async def create_rule(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
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
    if is_htmx_request(request):
        return await render_rules_list_response(
            request=request,
            session=session,
            context=context,
            recent_rule_id=rule.id,
        )
    return RedirectResponse(url=rule_anchor_url(rule.id), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/seed-defaults")
async def seed_default_rules(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> Response:
    await DefaultMerchantRuleSeeder(session).seed(context)
    if is_htmx_request(request):
        return await render_rules_list_response(
            request=request,
            session=session,
            context=context,
        )
    return RedirectResponse(url="/rules", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{rule_id}/edit", response_class=HTMLResponse)
async def edit_rule_form(
    request: Request,
    rule_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> HTMLResponse:
    return await render_rule_edit_panel_response(
        request=request,
        session=session,
        context=context,
        rule_id=rule_id,
    )


@router.post("/{rule_id}")
async def update_rule(
    request: Request,
    rule_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
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
    if is_htmx_request(request):
        return await render_rule_row_response(
            request=request,
            session=session,
            context=context,
            rule_id=rule.id,
        )
    return RedirectResponse(url=rule_anchor_url(rule.id), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{rule_id}/toggle")
async def toggle_rule(
    request: Request,
    rule_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    is_active: Annotated[bool, Form()] = False,
) -> Response:
    rule = await TransactionRuleManagementUseCase(session).set_rule_active(
        workspace_id=context.workspace.id,
        rule_id=rule_id,
        is_active=is_active,
    )
    if is_htmx_request(request):
        return await render_rule_row_response(
            request=request,
            session=session,
            context=context,
            rule_id=rule.id,
        )
    return RedirectResponse(url=rule_anchor_url(rule.id), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{rule_id}/delete")
async def delete_rule(
    request: Request,
    rule_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> Response:
    await TransactionRuleManagementUseCase(session).delete_rule(
        workspace_id=context.workspace.id,
        rule_id=rule_id,
    )
    if is_htmx_request(request):
        return await render_rules_list_response(
            request=request,
            session=session,
            context=context,
        )
    return RedirectResponse(url="/rules", status_code=status.HTTP_303_SEE_OTHER)


def rule_anchor_url(rule_id: UUID) -> str:
    return f"/rules#rule-{rule_id}"


async def render_rule_row_response(
    *,
    request: Request,
    session: AsyncSession,
    context: WorkspaceContext,
    rule_id: UUID,
) -> HTMLResponse:
    rule = await TransactionRuleQueryUseCase(session).get_rule(
        workspace_id=context.workspace.id,
        rule_id=rule_id,
    )
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    row = TransactionRulesPagePresenter.build_row(
        rule,
    )
    return templates.TemplateResponse(
        request,
        "transaction_rules/_rule_row.html",
        {
            "rule": row,
            "can_write": True,
        },
    )


async def render_rule_edit_panel_response(
    *,
    request: Request,
    session: AsyncSession,
    context: WorkspaceContext,
    rule_id: UUID,
) -> HTMLResponse:
    categories = await CategoryService(session).list_or_seed_defaults(
        context.workspace.id,
        context.workspace.type,
    )
    properties = await PropertyService(session).list_active(context.workspace.id)
    rule = await TransactionRuleQueryUseCase(session).get_rule(
        workspace_id=context.workspace.id,
        rule_id=rule_id,
    )
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    form = TransactionRulesPagePresenter.build_edit_form(
        rule,
        categories=categories,
        properties=properties,
    )
    return templates.TemplateResponse(
        request,
        "transaction_rules/_rule_edit_panel.html",
        {
            "form": form,
        },
    )


async def render_rules_list_response(
    *,
    request: Request,
    session: AsyncSession,
    context: WorkspaceContext,
    recent_rule_id: UUID | None = None,
) -> HTMLResponse:
    category_id = request.query_params.get("category_id")
    page = await build_rules_page(
        session=session,
        context=context,
        can_write=True,
        recent_rule_id=recent_rule_id,
        filter_search=request.query_params.get("q", ""),
        filter_category_id=parse_optional_filter_uuid(category_id),
        filter_status=request.query_params.get("status", "all"),
        limit=parse_rule_list_limit(request.query_params.get("limit")),
    )
    return templates.TemplateResponse(
        request,
        "transaction_rules/_rule_list_panel.html",
        {
            "page": page,
        },
    )


async def build_rules_page(
    *,
    session: AsyncSession,
    context: WorkspaceContext,
    can_write: bool,
    recent_rule_id: UUID | None = None,
    filter_search: str = "",
    filter_category_id: UUID | None = None,
    filter_status: str = "all",
    limit: int = RULE_LIST_DEFAULT_LIMIT,
) -> RulesPageVM:
    categories = await CategoryService(session).list_or_seed_defaults(
        context.workspace.id,
        context.workspace.type,
    )
    properties = await PropertyService(session).list_active(context.workspace.id)
    result = await TransactionRuleQueryUseCase(session).list_rules_for_page(
        workspace_id=context.workspace.id,
        search=filter_search,
        category_id=filter_category_id,
        status=filter_status,
        limit=limit,
        pinned_rule_id=recent_rule_id,
    )
    return TransactionRulesPagePresenter.build(
        result.rules,
        categories=categories,
        properties=properties,
        can_write=can_write,
        recent_rule_id=recent_rule_id,
        all_rule_count=result.total_count,
        filtered_rule_count=result.filtered_count,
        active_rule_count=result.active_count,
        inactive_rule_count=result.inactive_count,
        filter_search=filter_search,
        filter_category_id=filter_category_id,
        filter_status=filter_status,
        limit=result.limit,
    )


def is_htmx_request(request: Request) -> bool:
    return request.headers.get("hx-request") == "true"


def parse_optional_filter_uuid(raw_value: str | None) -> UUID | None:
    if not raw_value:
        return None
    try:
        return UUID(raw_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid category_id",
        ) from exc


def parse_rule_list_limit(raw_value: str | None) -> int:
    if raw_value is None:
        return RULE_LIST_DEFAULT_LIMIT
    try:
        return normalize_limit(int(raw_value))
    except ValueError:
        return RULE_LIST_DEFAULT_LIMIT
