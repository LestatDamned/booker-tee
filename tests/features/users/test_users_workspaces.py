from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    csrf_token_for_session,
    decode_access_token,
    decode_refresh_token,
    generate_token_pair,
    hash_password,
    hash_session_token,
    hash_token,
    verify_csrf_token,
    verify_password,
)
from app.core.settings import Settings
from app.features.users import service as users_service
from app.features.users.errors import InvalidRefreshTokenError, RefreshRaceError, UserError
from app.features.users.models import User, UserSession
from app.features.users.service import clean_user_name, normalize_email, validate_password
from app.features.users.sessions import summarize_user_agent
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


def test_historical_dashboard_redirects_to_react_app(client) -> None:
    response = client.get("/dashboard", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/app"


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


def test_password_validation_uses_configured_minimum() -> None:
    try:
        validate_password("eight888", minimum_length=12)
    except UserError as exc:
        assert "12" in str(exc)
    else:
        raise AssertionError("configured password minimum was ignored")


def test_password_validation_rejects_common_password() -> None:
    try:
        validate_password("Password123")
    except UserError as exc:
        assert "распространён" in str(exc)
    else:
        raise AssertionError("common password was accepted")


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


def test_access_and_refresh_jwts_are_typed_signed_and_expiring() -> None:
    settings = Settings(auth_secret_key="test-secret-that-is-at-least-32-bytes")
    user_id = uuid4()
    session_id = uuid4()
    tokens = generate_token_pair(
        user_id=user_id,
        session_id=session_id,
        settings=settings,
        refresh_expires_at=datetime(2027, 8, 4, 12, tzinfo=UTC),
    )
    encoded, signature = tokens.access_token.rsplit(".", 1)
    tampered_signature = ("A" if signature[0] != "A" else "B") + signature[1:]

    access_claims = decode_access_token(tokens.access_token, settings)
    refresh_claims = decode_refresh_token(tokens.refresh_token, settings)
    assert access_claims is not None and access_claims.user_id == user_id
    assert refresh_claims is not None and refresh_claims.session_id == session_id
    assert decode_refresh_token(tokens.access_token, settings) is None
    assert decode_access_token(f"{encoded}.{tampered_signature}", settings) is None


async def test_refresh_rotates_and_reuse_revokes_session(monkeypatch) -> None:
    current_time = [datetime(2026, 8, 4, 12, tzinfo=UTC)]

    class FakeSession:
        commit_count = 0

        async def commit(self) -> None:
            self.commit_count += 1

    class FakeUsers:
        async def get_session_for_refresh(self, _session_id):
            return user_session

        async def revoke_session(self, target: UserSession) -> None:
            target.revoked_at = current_time[0]

    class FakeRateLimits:
        async def increment(self, **_values) -> int:
            return 1

    monkeypatch.setattr(users_service, "utc_now", lambda: current_time[0])
    settings = Settings(auth_secret_key="test-secret-that-is-at-least-32-bytes")
    user = User(
        id=uuid4(),
        email="refresh@example.test",
        password_hash="hash",
        is_active=True,
    )
    user_session = UserSession(
        id=uuid4(),
        user_id=user.id,
        user=user,
        refresh_token_hash="pending",
        last_seen_at=current_time[0],
        expires_at=current_time[0] + timedelta(days=14),
    )
    original = generate_token_pair(
        user_id=user.id,
        session_id=user_session.id,
        refresh_expires_at=user_session.expires_at,
        settings=settings,
    )
    user_session.refresh_token_hash = hash_token(original.refresh_token)
    authentication = users_service.AuthenticationService(
        cast(AsyncSession, FakeSession()), settings
    )
    authentication.users = cast(users_service.UserRepository, FakeUsers())
    authentication.rate_limits = cast(users_service.AuthRateLimitRepository, FakeRateLimits())

    rotated = await authentication.refresh(original.refresh_token)

    assert rotated.refresh_token != original.refresh_token
    assert user_session.refresh_token_hash == hash_token(rotated.refresh_token)
    assert user_session.previous_refresh_token_hash == hash_token(original.refresh_token)
    with pytest.raises(RefreshRaceError):
        await authentication.refresh(original.refresh_token)
    assert user_session.revoked_at is None

    current_time[0] += timedelta(seconds=settings.refresh_reuse_grace_seconds + 1)
    with pytest.raises(InvalidRefreshTokenError):
        await authentication.refresh(original.refresh_token)
    assert user_session.revoked_at == current_time[0]


async def test_authenticated_session_touch_is_bounded(monkeypatch) -> None:
    now = datetime(2026, 8, 4, 12, tzinfo=UTC)

    class FakeSession:
        commit_count = 0

        async def commit(self) -> None:
            self.commit_count += 1

    class FakeUserRepository:
        def __init__(self, _session: FakeSession) -> None:
            pass

        async def get_active_session(self, **_values):
            return user_session

        async def revoke_session(self, _user_session: UserSession) -> None:
            raise AssertionError("active session must not be revoked")

    monkeypatch.setattr(users_service, "UserRepository", FakeUserRepository)
    monkeypatch.setattr(users_service, "utc_now", lambda: now)
    user = User(
        id=uuid4(),
        email="session@example.test",
        password_hash="hash",
        is_active=True,
    )
    user_session = UserSession(
        id=uuid4(),
        user_id=user.id,
        user=user,
        refresh_token_hash="hash",
        last_seen_at=now - timedelta(minutes=2),
        expires_at=now + timedelta(days=1),
    )
    session = FakeSession()
    authentication = users_service.AuthenticationService(
        cast(AsyncSession, session),
        Settings(auth_secret_key="test-secret-that-is-at-least-32-bytes"),
    )
    tokens = generate_token_pair(
        user_id=user.id,
        session_id=user_session.id,
        refresh_expires_at=datetime(2027, 8, 4, 12, tzinfo=UTC),
        settings=authentication.settings,
    )

    assert await authentication.resolve_authenticated_session(tokens.access_token) is not None
    assert session.commit_count == 0

    user_session.last_seen_at = now - timedelta(minutes=6)
    assert await authentication.resolve_authenticated_session(tokens.access_token) is not None
    assert user_session.last_seen_at == now
    assert session.commit_count == 1


async def test_idle_authenticated_session_is_revoked(monkeypatch) -> None:
    now = datetime(2026, 8, 4, 12, tzinfo=UTC)

    class FakeSession:
        commit_count = 0

        async def commit(self) -> None:
            self.commit_count += 1

    class FakeUserRepository:
        def __init__(self, _session: FakeSession) -> None:
            pass

        async def get_active_session(self, **_values):
            return user_session

        async def revoke_session(self, target: UserSession) -> None:
            target.revoked_at = now

    monkeypatch.setattr(users_service, "UserRepository", FakeUserRepository)
    monkeypatch.setattr(users_service, "utc_now", lambda: now)
    user = User(
        id=uuid4(),
        email="idle@example.test",
        password_hash="hash",
        is_active=True,
    )
    user_session = UserSession(
        id=uuid4(),
        user_id=user.id,
        user=user,
        refresh_token_hash="hash",
        last_seen_at=now - timedelta(hours=1, seconds=1),
        expires_at=now + timedelta(days=1),
    )
    session = FakeSession()
    authentication = users_service.AuthenticationService(
        cast(AsyncSession, session),
        Settings(auth_secret_key="test-secret-that-is-at-least-32-bytes"),
    )
    tokens = generate_token_pair(
        user_id=user.id,
        session_id=user_session.id,
        refresh_expires_at=datetime(2027, 8, 4, 12, tzinfo=UTC),
        settings=authentication.settings,
    )

    assert await authentication.resolve_authenticated_session(tokens.access_token) is None
    assert user_session.revoked_at == now
    assert session.commit_count == 1

    user_session.revoked_at = None
    user_session.last_seen_at = now
    user_session.expires_at = now
    assert await authentication.resolve_authenticated_session(tokens.access_token) is None
    assert user_session.revoked_at == now
    assert session.commit_count == 2


def test_user_agent_summary_is_allowlist_based() -> None:
    assert (
        summarize_user_agent(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
        )
        == "Chrome · Linux"
    )
    assert summarize_user_agent("PrivateClient/1.0 secret-data") == "Неизвестный браузер"
