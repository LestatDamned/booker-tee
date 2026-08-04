from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest

from api_client import ApiTestClient as TestClient
from app.core.config import get_settings
from app.db.session import get_session
from app.features.users.models import User
from app.features.workspaces.application.invitations import (
    AcceptedWorkspaceInvitation,
    WorkspaceInvitationService,
)
from app.features.workspaces.dependencies import (
    get_current_workspace_context,
)
from app.features.workspaces.errors import WorkspaceInvitationNotFoundError
from app.features.workspaces.models import (
    Workspace,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.service import WorkspaceContext
from app.main import create_app


def test_public_invitation_accept_rejects_missing_csrf() -> None:
    app = create_app()
    settings = get_settings()

    async def session_override() -> AsyncIterator[Any]:
        yield object()

    app.dependency_overrides[get_session] = session_override

    with TestClient(app) as client:
        client.cookies.set(settings.session_cookie_name, "workspace-security-session")
        response = client.post(
            "/workspaces/invitations/invitation-token/accept",
            follow_redirects=False,
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Недействительный CSRF токен."}


def test_public_invitation_preview_does_not_cache_or_forward_token_referrer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()

    async def session_override() -> AsyncIterator[Any]:
        yield object()

    async def invalid_preview(self, *, invitation_token: str):
        raise WorkspaceInvitationNotFoundError("Приглашение не найдено или уже недействительно.")

    monkeypatch.setattr(WorkspaceInvitationService, "preview", invalid_preview)
    app.dependency_overrides[get_session] = session_override

    with TestClient(app) as client:
        response = client.get("/workspaces/invitations/private-token")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"


@pytest.mark.parametrize("available", [True, False])
def test_invitation_accept_uses_actor_and_returns_safe_navigation(
    monkeypatch: pytest.MonkeyPatch,
    available: bool,
) -> None:
    app = create_app()
    settings = get_settings()
    user_id = uuid4()
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=User(
            id=user_id,
            email="member@example.test",
            password_hash="hash",
            name="Member",
        ),
        workspace=Workspace(
            id=uuid4(),
            owner_id=user_id,
            name="Personal",
            type=WorkspaceType.PERSONAL,
            default_currency="RUB",
        ),
        membership=WorkspaceMember(
            workspace_id=uuid4(),
            user_id=user_id,
            role=WorkspaceRole.OWNER,
            status=WorkspaceMemberStatus.ACTIVE,
        ),
    )
    accepted: dict[str, Any] = {}

    async def session_override() -> AsyncIterator[Any]:
        yield object()

    async def context_override() -> WorkspaceContext:
        return context

    async def accept(self, **values):
        accepted.update(values)
        if not available:
            raise WorkspaceInvitationNotFoundError(
                "Приглашение не найдено или уже недействительно."
            )
        return AcceptedWorkspaceInvitation(workspace_id=workspace_id)

    monkeypatch.setattr(WorkspaceInvitationService, "accept", accept)
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_current_workspace_context] = context_override

    with TestClient(app) as client:
        client.cookies.set(settings.session_cookie_name, "session-token")
        response = client.post(
            "/workspaces/invitations/private-token/accept",
            follow_redirects=False,
        )

    assert accepted == {
        "actor_user_id": user_id,
        "invitation_token": "private-token",
        "session_token": "session-token",
    }
    assert response.status_code == 303
    assert response.headers["location"] == (
        "/app/workspaces" if available else "/workspaces/invitations/private-token"
    )
