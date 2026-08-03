from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest

from api_client import ApiTestClient as TestClient
from app.core.config import get_settings
from app.db.session import get_session
from app.features.users.models import User
from app.features.workspaces.dependencies import require_member_management_context
from app.features.workspaces.models import (
    Workspace,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.service import WorkspaceContext
from app.main import create_app


@pytest.mark.parametrize(
    ("path", "form"),
    [
        ("/workspaces", {"name": "Family"}),
        (
            "/workspaces/{workspace_id}",
            {"name": "Family", "workspace_type": "personal", "default_currency": "RUB"},
        ),
        ("/workspaces/{workspace_id}/select", {}),
        ("/workspaces/{workspace_id}/invitations", {"role": "viewer"}),
        ("/workspaces/{workspace_id}/invitations/{resource_id}/revoke", {}),
        ("/workspaces/{workspace_id}/members/{resource_id}/role", {"role": "viewer"}),
        ("/workspaces/{workspace_id}/members/{resource_id}/disable", {}),
        ("/workspaces/{workspace_id}/members/{resource_id}/reactivate", {}),
        ("/workspaces/invitations/invitation-token/accept", {}),
    ],
)
def test_authenticated_workspace_post_routes_reject_missing_csrf(
    path: str,
    form: dict[str, str],
) -> None:
    app = create_app()
    settings = get_settings()
    workspace_id = uuid4()
    resource_id = uuid4()

    async def session_override() -> AsyncIterator[Any]:
        yield object()

    app.dependency_overrides[get_session] = session_override

    with TestClient(app) as client:
        client.cookies.set(settings.session_cookie_name, "workspace-security-session")
        response = client.post(
            path.format(workspace_id=workspace_id, resource_id=resource_id),
            data=form,
            follow_redirects=False,
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Недействительный CSRF токен."}


@pytest.mark.parametrize(
    ("path", "form"),
    [
        ("/workspaces/{workspace_id}/invitations", {"role": "viewer"}),
        ("/workspaces/{workspace_id}/invitations/{resource_id}/revoke", {}),
        ("/workspaces/{workspace_id}/members/{resource_id}/role", {"role": "viewer"}),
        ("/workspaces/{workspace_id}/members/{resource_id}/disable", {}),
        ("/workspaces/{workspace_id}/members/{resource_id}/reactivate", {}),
    ],
)
def test_member_management_routes_mask_non_current_workspace_before_resource_lookup(
    path: str,
    form: dict[str, str],
) -> None:
    app = create_app()
    current_workspace_id = uuid4()
    foreign_workspace_id = uuid4()
    resource_id = uuid4()

    async def session_override() -> AsyncIterator[Any]:
        yield object()

    async def context_override() -> WorkspaceContext:
        user_id = uuid4()
        return WorkspaceContext(
            user=User(
                id=user_id,
                email="owner@example.test",
                password_hash="hash",
                name="Owner",
            ),
            workspace=Workspace(
                id=current_workspace_id,
                owner_id=user_id,
                name="Current",
                type=WorkspaceType.PERSONAL,
                default_currency="RUB",
            ),
            membership=WorkspaceMember(
                workspace_id=current_workspace_id,
                user_id=user_id,
                role=WorkspaceRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
            ),
        )

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_member_management_context] = context_override

    with TestClient(app) as client:
        response = client.post(
            path.format(workspace_id=foreign_workspace_id, resource_id=resource_id),
            data=form,
            follow_redirects=False,
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
