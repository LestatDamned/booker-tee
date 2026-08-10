from collections.abc import AsyncIterator
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from api_client import ApiTestClient as TestClient
from app.api.dependencies import get_authenticated_session_context
from app.api.v1.workspaces.dependencies import get_workspace_invitation_service
from app.core.config import get_settings
from app.db.session import get_session
from app.features.users.models import User
from app.features.workspaces.application.invitations import (
    AcceptedWorkspaceInvitation,
    PublicWorkspaceInvitation,
)
from app.features.workspaces.domain.types import WorkspaceRole
from app.features.workspaces.errors import (
    WorkspaceInvitationNotFoundError,
    WorkspaceInvitationTransitionError,
)
from app.main import create_app


class InvitationServiceStub:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.accepted: dict[str, Any] = {}
        self.accept_error: WorkspaceInvitationTransitionError | None = None

    async def preview(self, *, invitation_token: str) -> PublicWorkspaceInvitation:
        if not self.available:
            raise WorkspaceInvitationNotFoundError(
                "Приглашение не найдено или уже недействительно."
            )
        return PublicWorkspaceInvitation(
            workspace_name="Семейный бюджет",
            role=WorkspaceRole.VIEWER,
            expires_at=datetime.fromisoformat("2026-08-08T12:00:00+00:00"),
        )

    async def accept(self, **values: Any) -> AcceptedWorkspaceInvitation:
        self.accepted.update(values)
        if not self.available:
            raise WorkspaceInvitationNotFoundError(
                "Приглашение не найдено или уже недействительно."
            )
        if self.accept_error is not None:
            raise self.accept_error
        return AcceptedWorkspaceInvitation(workspace_id=uuid4())


def test_public_invitation_accept_rejects_missing_csrf() -> None:
    app = create_app()
    settings = get_settings()

    async def session_override() -> AsyncIterator[Any]:
        yield object()

    app.dependency_overrides[get_session] = session_override

    with TestClient(app) as client:
        client.cookies.set(settings.session_cookie_name, "workspace-security-session")
        response = client.post(
            "/api/v1/workspaces/invitations/invitation-token/accept",
        )

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "invalid_csrf",
        "message": "Недействительный CSRF токен.",
    }


@pytest.mark.parametrize("available", [True, False])
def test_public_invitation_preview_is_private_and_masked(available: bool) -> None:
    app = create_app()
    service = InvitationServiceStub(available=available)
    app.dependency_overrides[get_workspace_invitation_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/workspaces/invitations/private-token")

    assert response.status_code == (200 if available else 404)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    if available:
        assert response.json()["workspaceName"] == "Семейный бюджет"
        assert "token" not in response.text.lower()
    else:
        assert response.json()["error"]["code"] == "invitation_not_found"


@pytest.mark.parametrize("available", [True, False])
def test_invitation_accept_uses_actor_and_returns_safe_navigation(available: bool) -> None:
    app = create_app()
    service = InvitationServiceStub(available=available)
    user_id = uuid4()
    user = User(
        id=user_id,
        email="member@example.test",
        password_hash="hash",
        name="Member",
    )
    app.dependency_overrides[get_workspace_invitation_service] = lambda: service
    app.dependency_overrides[get_authenticated_session_context] = lambda: SimpleNamespace(
        user=user,
        session_token="session-token",
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workspaces/invitations/private-token/accept",
        )

    assert service.accepted == {
        "actor_user_id": user_id,
        "invitation_token": "private-token",
        "session_token": "session-token",
    }
    assert response.status_code == (200 if available else 404)
    assert response.headers["Cache-Control"] == "no-store"
    if available:
        assert response.json()["navigationOutcome"] == {
            "kind": "workspace_changed",
            "href": "/app/workspaces",
            "boundary": "hard_reload",
        }
    else:
        assert response.json()["error"]["code"] == "invitation_not_found"


def test_invitation_accept_rejects_wrong_account_without_leaking_email() -> None:
    app = create_app()
    service = InvitationServiceStub()
    service.accept_error = WorkspaceInvitationTransitionError(
        "Приглашение предназначено для другого аккаунта.",
        reason_codes=["invitation_email_mismatch"],
    )
    user = User(
        id=uuid4(),
        email="wrong@example.test",
        password_hash="hash",
        name="Wrong account",
    )
    app.dependency_overrides[get_workspace_invitation_service] = lambda: service
    app.dependency_overrides[get_authenticated_session_context] = lambda: SimpleNamespace(
        user=user,
        session_token="session-token",
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workspaces/invitations/private-token/accept",
        )

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "invitation_email_mismatch",
        "message": "Приглашение предназначено для другого аккаунта.",
        "details": {"reasonCodes": ["invitation_email_mismatch"]},
    }
    assert "invitee" not in response.text
