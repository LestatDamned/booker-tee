from email.message import EmailMessage
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    auth_rate_limit_bucket_hash,
    generate_user_token,
    hash_user_token,
)
from app.core.settings import Settings
from app.features.users.email_delivery import (
    IdentityEmail,
    build_email_change_messages,
    build_email_verification_message,
    build_password_reset_message,
    send_identity_email,
)
from app.features.users.email_verification import EmailVerificationService
from app.features.users.errors import SignupsClosedError


def test_user_tokens_and_rate_limit_keys_do_not_expose_secrets() -> None:
    settings = Settings(auth_secret_key="identity-foundations-test-secret")
    token = generate_user_token()
    token_hash = hash_user_token(token)
    account_bucket = auth_rate_limit_bucket_hash(
        scope="login-account",
        key="max@example.test",
        settings=settings,
    )
    network_bucket = auth_rate_limit_bucket_hash(
        scope="login-network",
        key="127.0.0.1",
        settings=settings,
    )

    assert len(token_hash) == 64
    assert token not in token_hash
    assert account_bucket != network_bucket
    assert "max@example.test" not in account_bucket
    assert "127.0.0.1" not in network_bucket


def test_verification_email_preserves_only_validated_site_relative_continuation() -> None:
    message = build_email_verification_message(
        recipient="max@example.test",
        token="secret-token",
        base_url="https://booker.example/",
        next_path="/workspaces/invitations/example",
    )

    assert (
        "https://booker.example/app/auth/verify-email#"
        "token=secret-token&next=%2Fworkspaces%2Finvitations%2Fexample"
    ) in message.text


def test_identity_bearer_tokens_use_url_fragments() -> None:
    marker = "marker-token-not-for-access-logs"
    reset = build_password_reset_message(
        recipient="max@example.test",
        token=marker,
        base_url="https://booker.example",
    )
    _, email_change = build_email_change_messages(
        current_email="old@example.test",
        target_email="new@example.test",
        token=marker,
        base_url="https://booker.example",
    )

    assert f"/app/auth/reset-password#token={marker}" in reset.text
    assert f"/app/profile/account#token={marker}" in email_change.text
    assert f"?token={marker}" not in reset.text + email_change.text


def test_production_signups_require_identity_delivery_to_be_enabled() -> None:
    settings = Settings(
        environment="production",
        auth_secret_key="production-secret-value-with-enough-entropy",
        session_cookie_secure=True,
        allowed_hosts=["booker.example"],
        registration_mode="open",
        identity_email_enabled=False,
    )

    with pytest.raises(RuntimeError, match="BOOKER_TEE_IDENTITY_EMAIL_ENABLED"):
        settings.validate_for_runtime()


@pytest.mark.asyncio
async def test_invite_only_signup_rejects_missing_invitation(monkeypatch) -> None:
    commit = AsyncMock()
    session = cast(AsyncSession, SimpleNamespace(commit=commit))
    service = EmailVerificationService(
        session,
        Settings(registration_mode="invite_only"),
    )
    monkeypatch.setattr(service, "_enforce_signup_limit", AsyncMock())

    with pytest.raises(SignupsClosedError, match="только по приглашению"):
        await service.request_signup(
            email="invitee@example.test",
            password="correct horse battery staple",
            name=None,
            base_url="https://booker.example",
        )

    commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_smtp_delivery_uses_starttls_and_hides_sensitive_repr(monkeypatch) -> None:
    sent: list[EmailMessage] = []
    events: list[str] = []

    class FakeSmtp:
        def __init__(self, host: str, port: int, *, timeout: int) -> None:
            assert (host, port, timeout) == ("smtp.example.test", 587, 10)

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def starttls(self, *, context: object) -> None:
            assert context is not None
            events.append("starttls")

        def login(self, username: str, password: str) -> None:
            assert (username, password) == ("booker", "smtp-secret")
            events.append("login")

        def send_message(self, message: EmailMessage) -> None:
            sent.append(message)

    async def run_inline(function, *args):
        return function(*args)

    monkeypatch.setattr("app.features.users.email_delivery.smtplib.SMTP", FakeSmtp)
    monkeypatch.setattr("app.features.users.email_delivery.asyncio.to_thread", run_inline)
    message = IdentityEmail(
        recipient="max@example.test",
        subject="Подтвердите email",
        text="https://booker.example/app/auth/verify-email#token=secret-token",
    )

    await send_identity_email(
        message,
        Settings(
            identity_email_from="Booker Tee <identity@booker.example>",
            smtp_host="smtp.example.test",
            smtp_username="booker",
            smtp_password="smtp-secret",
        ),
    )

    assert events == ["starttls", "login"]
    assert sent[0]["To"] == "max@example.test"
    assert "secret-token" in sent[0].get_content()
    assert "max@example.test" not in repr(message)
    assert "secret-token" not in repr(message)


def test_production_identity_email_requires_https_sender_and_smtp() -> None:
    missing = Settings(
        environment="production",
        auth_secret_key="production-secret-value-with-enough-entropy",
        session_cookie_secure=True,
        allowed_hosts=["booker.example"],
        identity_email_enabled=True,
    )

    with pytest.raises(RuntimeError) as error:
        missing.validate_for_runtime()

    assert "BOOKER_TEE_PUBLIC_BASE_URL" in str(error.value)
    assert "BOOKER_TEE_IDENTITY_EMAIL_FROM" in str(error.value)
    assert "BOOKER_TEE_SMTP_HOST" in str(error.value)

    configured = Settings(
        environment="production",
        auth_secret_key="production-secret-value-with-enough-entropy",
        session_cookie_secure=True,
        allowed_hosts=["booker.example"],
        identity_email_enabled=True,
        identity_email_from="identity@booker.example",
        smtp_host="smtp.example.test",
        public_base_url="https://booker.example",
    )
    configured.validate_for_runtime()
