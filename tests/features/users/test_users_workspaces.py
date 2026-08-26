from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

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

COOKIE_ID = UUID("11111111-1111-1111-1111-111111111111")


def test_normalize_email_lowercases_and_trims() -> None:
    assert normalize_email("  MAX@Example.COM ") == "max@example.com"


def test_normalize_email_rejects_invalid_email() -> None:
    with pytest.raises(UserError, match="email"):
        normalize_email("not-email")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        pytest.param("  Max  ", "Max", id="trimmed"),
        pytest.param("   ", None, id="blank"),
        pytest.param(None, None, id="missing"),
    ],
)
def test_clean_user_name(name: str | None, expected: str | None) -> None:
    assert clean_user_name(name) == expected


def test_workspace_name_is_normalized() -> None:
    assert clean_workspace_name("  Family ") == "Family"


def test_workspace_currency_is_normalized() -> None:
    assert normalize_currency(" rub ") == "RUB"


def test_workspace_currency_rejects_invalid_code() -> None:
    with pytest.raises(WorkspaceError, match="Валюта"):
        normalize_currency("rouble")


@pytest.mark.parametrize(
    ("cookie_name", "expected"),
    [
        pytest.param("good", COOKIE_ID, id="valid"),
        pytest.param("bad", None, id="invalid"),
        pytest.param("missing", None, id="missing"),
    ],
)
def test_parse_uuid_cookie_ignores_missing_or_invalid_values(
    cookie_name: str,
    expected: UUID | None,
) -> None:
    request = Request(
        {
            "type": "http",
            "headers": [(b"cookie", f"good={COOKIE_ID}; bad=not-a-uuid".encode())],
        }
    )

    assert parse_uuid_cookie(request, cookie_name) == expected


def test_passwords_are_hashed_and_verified() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


@pytest.mark.parametrize(
    ("password", "minimum_length", "message"),
    [
        pytest.param("short", 8, "Пароль", id="too-short"),
        pytest.param("eight888", 12, "12", id="configured-minimum"),
        pytest.param("Password123", 8, "распространён", id="common-password"),
    ],
)
def test_password_validation_rejects_unsafe_values(
    password: str,
    minimum_length: int,
    message: str,
) -> None:
    with pytest.raises(UserError, match=message):
        validate_password(password, minimum_length=minimum_length)


def test_session_token_hash_is_deterministic_and_not_plaintext() -> None:
    session_token = "session-token"

    token_hash = hash_session_token(session_token)

    assert token_hash == hash_session_token(session_token)
    assert token_hash != session_token


def test_csrf_token_is_bound_to_session() -> None:
    settings = Settings(auth_secret_key="test-secret")
    session_token = "session-token"
    csrf_token = csrf_token_for_session(session_token, settings)

    assert csrf_token == csrf_token_for_session(session_token, settings)
    assert verify_csrf_token(
        provided_token=csrf_token,
        session_token=session_token,
        settings=settings,
    )
    assert not verify_csrf_token(
        provided_token=csrf_token,
        session_token="other-session-token",
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
    current_time = [datetime.now(UTC)]

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


@pytest.mark.parametrize(
    ("last_seen_ago", "touched"),
    [
        pytest.param(timedelta(minutes=2), False, id="recent"),
        pytest.param(timedelta(minutes=6), True, id="touch-due"),
    ],
)
async def test_authenticated_session_touch_is_bounded(
    monkeypatch,
    last_seen_ago: timedelta,
    touched: bool,
) -> None:
    now = datetime(2026, 8, 4, 12, tzinfo=UTC)
    last_seen_at = now - last_seen_ago
    user_session, authentication, commit, access_token = authenticated_session_harness(
        monkeypatch,
        now=now,
        last_seen_at=last_seen_at,
        expires_at=now + timedelta(days=1),
    )

    assert await authentication.resolve_authenticated_session(access_token) is not None
    assert user_session.last_seen_at == (now if touched else last_seen_at)
    assert user_session.revoked_at is None
    if touched:
        commit.assert_awaited_once_with()
    else:
        commit.assert_not_awaited()


@pytest.mark.parametrize(
    ("last_seen_ago", "expires_in"),
    [
        pytest.param(timedelta(hours=12, seconds=1), timedelta(days=1), id="idle"),
        pytest.param(timedelta(0), timedelta(0), id="expired"),
    ],
)
async def test_unusable_authenticated_session_is_revoked(
    monkeypatch,
    last_seen_ago: timedelta,
    expires_in: timedelta,
) -> None:
    now = datetime(2026, 8, 4, 12, tzinfo=UTC)
    user_session, authentication, commit, access_token = authenticated_session_harness(
        monkeypatch,
        now=now,
        last_seen_at=now - last_seen_ago,
        expires_at=now + expires_in,
    )

    assert await authentication.resolve_authenticated_session(access_token) is None
    assert user_session.revoked_at == now
    commit.assert_awaited_once_with()


def authenticated_session_harness(
    monkeypatch,
    *,
    now: datetime,
    last_seen_at: datetime,
    expires_at: datetime,
):
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
        last_seen_at=last_seen_at,
        expires_at=expires_at,
    )

    class FakeUserRepository:
        async def get_active_session(self, **_values):
            return user_session

        async def revoke_session(self, target: UserSession) -> None:
            target.revoked_at = now

    monkeypatch.setattr(users_service, "utc_now", lambda: now)
    commit = AsyncMock()
    authentication = users_service.AuthenticationService(
        cast(AsyncSession, SimpleNamespace(commit=commit)),
        Settings(auth_secret_key="test-secret-that-is-at-least-32-bytes"),
    )
    authentication.users = cast(users_service.UserRepository, FakeUserRepository())
    tokens = generate_token_pair(
        user_id=user.id,
        session_id=user_session.id,
        refresh_expires_at=datetime(2027, 8, 4, 12, tzinfo=UTC),
        settings=authentication.settings,
    )
    return user_session, authentication, commit, tokens.access_token


@pytest.mark.parametrize(
    ("user_agent", "expected"),
    [
        pytest.param(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "Chrome/126.0 Safari/537.36",
            "Chrome · Linux",
            id="known-browser",
        ),
        pytest.param(
            "PrivateClient/1.0 secret-data",
            "Неизвестный браузер",
            id="unknown-client",
        ),
    ],
)
def test_user_agent_summary_is_allowlist_based(user_agent: str, expected: str) -> None:
    assert summarize_user_agent(user_agent) == expected
