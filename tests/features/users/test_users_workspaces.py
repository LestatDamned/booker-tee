from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    csrf_token_for_session,
    hash_password,
    hash_session_token,
    verify_csrf_token,
    verify_password,
)
from app.core.settings import Settings
from app.features.users import service as users_service
from app.features.users.errors import UserError
from app.features.users.service import clean_user_name, normalize_email, validate_password
from app.features.workspaces.dependencies import parse_uuid_cookie
from app.features.workspaces.errors import WorkspaceError
from app.features.workspaces.models import (
    WorkspaceAuditEventType,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.router import safe_workspace_return_path
from app.features.workspaces.service import clean_workspace_name, normalize_currency


def test_normalize_email_lowercases_and_trims() -> None:
    assert normalize_email("  MAX@Example.COM ") == "max@example.com"


def test_normalize_email_rejects_invalid_email() -> None:
    try:
        normalize_email("not-email")
    except UserError as exc:
        assert "email" in str(exc)
    else:
        raise AssertionError("invalid email was accepted")


def test_clean_user_name_turns_blank_into_none() -> None:
    assert clean_user_name("  Max  ") == "Max"
    assert clean_user_name("   ") is None
    assert clean_user_name(None) is None


def test_workspace_name_and_currency_are_normalized() -> None:
    assert clean_workspace_name("  Family ") == "Family"
    assert normalize_currency(" rub ") == "RUB"


def test_workspace_currency_rejects_invalid_code() -> None:
    try:
        normalize_currency("rouble")
    except WorkspaceError as exc:
        assert "Валюта" in str(exc)
    else:
        raise AssertionError("invalid currency was accepted")


def test_parse_uuid_cookie_ignores_missing_or_invalid_values() -> None:
    valid_id = uuid4()
    request = Request(
        {
            "type": "http",
            "headers": [(b"cookie", f"good={valid_id}; bad=not-a-uuid".encode())],
        }
    )

    assert parse_uuid_cookie(request, "good") == valid_id
    assert parse_uuid_cookie(request, "bad") is None
    assert parse_uuid_cookie(request, "missing") is None


def test_financial_pages_redirect_to_login_without_session(client) -> None:
    response = client.get(
        "/accounts/11111111-1111-1111-1111-111111111111",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_dashboard_redirects_to_login_without_session(client) -> None:
    response = client.get("/dashboard", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_form_keeps_safe_next_path(client) -> None:
    response = client.get("/login?next=/workspaces/invitations/invite-token")

    assert response.status_code == 200
    assert 'name="next" value="/workspaces/invitations/invite-token"' in response.text


def test_login_form_rejects_external_next_path(client) -> None:
    response = client.get("/login?next=https://example.com/phishing")

    assert response.status_code == 200
    assert 'name="next" value="/workspaces"' in response.text
    assert "https://example.com/phishing" not in response.text


def test_workspace_selection_return_path_must_be_local() -> None:
    assert safe_workspace_return_path("/imports?status=needs_review") == (
        "/imports?status=needs_review"
    )
    assert safe_workspace_return_path("https://example.com/phishing") == "/workspaces"
    assert safe_workspace_return_path("//example.com/phishing") == "/workspaces"
    assert safe_workspace_return_path(None) == "/workspaces"


def test_passwords_are_hashed_and_verified() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_password_validation_rejects_short_password() -> None:
    try:
        validate_password("short")
    except UserError as exc:
        assert "Пароль" in str(exc)
    else:
        raise AssertionError("short password was accepted")


def test_session_token_hash_and_csrf_are_deterministic() -> None:
    settings = Settings(auth_secret_key="test-secret")
    session_token = "session-token"

    csrf_token = csrf_token_for_session(session_token, settings)

    assert hash_session_token(session_token) == hash_session_token(session_token)
    assert csrf_token == csrf_token_for_session(session_token, settings)
    assert verify_csrf_token(
        provided_token=csrf_token,
        session_token=session_token,
        settings=settings,
    )
    assert not verify_csrf_token(
        provided_token="bad",
        session_token=session_token,
        settings=settings,
    )


async def test_registration_creates_workspace_membership_and_session_once(monkeypatch) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.commit_count = 0
            self.created_user = None
            self.created_session = None

        async def commit(self) -> None:
            self.commit_count += 1

    class FakeUserRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def get_by_email(self, email: str):
            return None

        async def create(self, *, email: str, password_hash: str, name: str | None = None):
            user = SimpleNamespace(
                id=uuid4(),
                email=email,
                password_hash=password_hash,
                name=name,
                is_active=True,
            )
            self.session.created_user = user
            return user

        async def create_session(self, user_session):
            self.session.created_session = user_session
            return user_session

    class FakeWorkspaceRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session
            self.audit_events = []

        async def create_personal_workspace_with_owner_membership(self, user_id):
            workspace = SimpleNamespace(
                id=uuid4(),
                owner_id=user_id,
                name="Personal",
                type=WorkspaceType.PERSONAL,
                default_currency="RUB",
                is_active=True,
            )
            membership = SimpleNamespace(
                id=uuid4(),
                workspace_id=workspace.id,
                user_id=user_id,
                role=WorkspaceRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
                workspace=workspace,
            )
            return workspace, membership

        async def create_audit_event(self, **values):
            event = SimpleNamespace(id=uuid4(), **values)
            self.audit_events.append(event)
            return event

    monkeypatch.setattr(users_service, "UserRepository", FakeUserRepository)
    monkeypatch.setattr(users_service, "WorkspaceRepository", FakeWorkspaceRepository)

    session = FakeSession()
    auth = users_service.AuthenticationService(
        cast(AsyncSession, session),
        Settings(auth_secret_key="test-secret"),
    )

    login_session = await auth.register(
        email="  MAX@example.COM ",
        password="correct horse battery staple",
        name="  Max  ",
    )

    assert session.commit_count == 1
    assert login_session.user.email == "max@example.com"
    assert login_session.user.name == "Max"
    assert login_session.workspace.owner_id == login_session.user.id
    assert login_session.membership.user_id == login_session.user.id
    assert login_session.membership.workspace_id == login_session.workspace.id
    assert login_session.session.current_workspace_id == login_session.workspace.id
    assert login_session.session.user_id == login_session.user.id
    assert session.created_session is login_session.session
    repository = cast(Any, auth.workspaces)
    assert len(repository.audit_events) == 1
    assert repository.audit_events[0].event_type == WorkspaceAuditEventType.WORKSPACE_CREATED
    assert repository.audit_events[0].workspace_id == login_session.workspace.id
