from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.v1.session.schemas import (
    SessionCapabilities,
    SessionMembership,
    SessionResponse,
    SessionUser,
    SessionWorkspace,
)
from app.features.workspaces.permissions import permission_flags_for

router = APIRouter(tags=["session"])


@router.get("/session", response_model=SessionResponse)
async def read_session(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
) -> SessionResponse:
    workspace_context = context.workspace
    permission_flags = permission_flags_for(workspace_context.membership)
    return SessionResponse(
        user=SessionUser(
            id=workspace_context.user.id,
            email=workspace_context.user.email,
            name=workspace_context.user.name,
        ),
        workspace=SessionWorkspace(
            id=workspace_context.workspace.id,
            name=workspace_context.workspace.name,
            type=workspace_context.workspace.type,
            default_currency=workspace_context.workspace.default_currency,
        ),
        membership=SessionMembership(
            role=workspace_context.membership.role,
            status=workspace_context.membership.status,
        ),
        capabilities=SessionCapabilities(
            can_read_workspace=permission_flags.can_read_workspace,
            can_write_financial_data=permission_flags.can_write_financial_data,
            can_manage_imports=permission_flags.can_manage_imports,
            can_manage_members=permission_flags.can_manage_members,
            can_manage_workspace=permission_flags.can_manage_workspace,
        ),
        csrf_token=context.csrf_token,
    )
