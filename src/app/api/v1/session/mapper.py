from app.api.dependencies import ApiRequestContext
from app.api.v1.session.responses import (
    SessionApiResponse,
    SessionCapabilitiesApiResponse,
    SessionMembershipApiResponse,
    SessionUserApiResponse,
    SessionWorkspaceApiResponse,
)
from app.features.workspaces.permissions import permission_flags_for
from app.features.workspaces.service import WorkspaceContext


class SessionApiResponseMapper:
    @staticmethod
    def from_context(context: ApiRequestContext) -> SessionApiResponse:
        return SessionApiResponseMapper.from_workspace_context(
            context.workspace,
            csrf_token=context.csrf_token,
        )

    @staticmethod
    def from_workspace_context(
        workspace_context: WorkspaceContext,
        *,
        csrf_token: str,
    ) -> SessionApiResponse:
        permission_flags = permission_flags_for(workspace_context.membership)
        return SessionApiResponse(
            user=SessionUserApiResponse(
                id=workspace_context.user.id,
                email=workspace_context.user.email,
                name=workspace_context.user.name,
            ),
            workspace=SessionWorkspaceApiResponse(
                id=workspace_context.workspace.id,
                name=workspace_context.workspace.name,
                type=workspace_context.workspace.type,
                default_currency=workspace_context.workspace.default_currency,
            ),
            membership=SessionMembershipApiResponse(
                role=workspace_context.membership.role,
                status=workspace_context.membership.status,
            ),
            capabilities=SessionCapabilitiesApiResponse(
                can_read_workspace=permission_flags.can_read_workspace,
                can_write_financial_data=permission_flags.can_write_financial_data,
                can_manage_imports=permission_flags.can_manage_imports,
                can_view_raw_import_data=permission_flags.can_view_raw_import_data,
                can_view_member_directory=permission_flags.can_view_member_directory,
                can_manage_members=permission_flags.can_manage_members,
                can_view_workspace_activity=permission_flags.can_view_workspace_activity,
                can_manage_workspace=permission_flags.can_manage_workspace,
            ),
            csrf_token=csrf_token,
        )
