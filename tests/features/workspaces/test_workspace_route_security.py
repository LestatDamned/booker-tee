from datetime import datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI

from api_client import ApiTestClient as TestClient
from app.api.dependencies import get_authenticated_session_context
from app.api.v1.workspaces.dependencies import get_workspace_invitation_service
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


def test_public_invitation_accept_requires_bearer_access_token(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workspaces/invitations/accept",
            json={"invitationToken": "marker-invitation-token"},
        )

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "unauthorized",
        "message": "Требуется вход.",
    }


@pytest.mark.parametrize(
    "available",
    [
        pytest.param(True, id="available"),
        pytest.param(False, id="masked-not-found"),
    ],
)
def test_public_invitation_preview_is_private_and_masked(
    app: FastAPI,
    available: bool,
) -> None:
    service = InvitationServiceStub(available=available)
    app.dependency_overrides[get_workspace_invitation_service] = lambda: service

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workspaces/invitations/preview",
            json={"invitationToken": "marker-invitation-token"},
        )

    assert response.status_code == (200 if available else 404)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "marker-invitation-token" not in str(response.request.url)
    if available:
        assert response.json()["workspaceName"] == "Семейный бюджет"
        assert "token" not in response.text.lower()
    else:
        assert response.json()["error"]["code"] == "invitation_not_found"


@pytest.mark.parametrize(
    "available",
    [
        pytest.param(True, id="accepted"),
        pytest.param(False, id="masked-not-found"),
    ],
)
def test_invitation_accept_uses_actor_and_returns_safe_navigation(
    app: FastAPI,
    available: bool,
) -> None:
    service = InvitationServiceStub(available=available)
    user_id = uuid4()
    session_id = uuid4()
    user = User(
        id=user_id,
        email="member@example.test",
        password_hash="hash",
        name="Member",
    )
    app.dependency_overrides[get_workspace_invitation_service] = lambda: service
    app.dependency_overrides[get_authenticated_session_context] = lambda: SimpleNamespace(
        user=user,
        session_id=session_id,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workspaces/invitations/accept",
            json={"invitationToken": "private-token"},
        )

    assert service.accepted == {
        "actor_user_id": user_id,
        "invitation_token": "private-token",
        "session_token": session_id,
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


def test_invitation_accept_rejects_wrong_account_without_leaking_email(
    app: FastAPI,
) -> None:
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
        session_id=uuid4(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workspaces/invitations/accept",
            json={"invitationToken": "private-token"},
        )

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "invitation_email_mismatch",
        "message": "Приглашение предназначено для другого аккаунта.",
        "details": {"reasonCodes": ["invitation_email_mismatch"]},
    }
    assert "invitee" not in response.text
