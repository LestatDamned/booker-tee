from uuid import uuid4

from fastapi import Request

from app.core.security import (
    csrf_token_for_session,
    hash_password,
    hash_session_token,
    verify_csrf_token,
    verify_password,
)
from app.core.settings import Settings
from app.features.users.errors import UserError
from app.features.users.service import clean_user_name, normalize_email, validate_password
from app.features.workspaces.dependencies import parse_uuid_cookie
from app.features.workspaces.errors import WorkspaceError
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
    response = client.get("/accounts", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_dashboard_redirects_to_login_without_session(client) -> None:
    response = client.get("/dashboard", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


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
