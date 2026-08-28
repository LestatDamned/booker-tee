import asyncio
from pathlib import Path
from time import monotonic

import pytest
from fastapi import FastAPI

from api_client import ApiTestClient as TestClient
from app.core.settings import Settings
from app.main import create_app, lifespan


def test_home_redirects_to_react_app(client: TestClient) -> None:
    response = client.get(
        "/",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "/app"


def test_healthcheck_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Booker Tee"}


def test_security_headers_are_set(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "same-origin"


def test_allowed_hosts_accepts_comma_separated_env(monkeypatch) -> None:
    monkeypatch.setenv("BOOKER_TEE_ALLOWED_HOSTS", "app.example.com,127.0.0.1")
    monkeypatch.setenv("BOOKER_TEE_DEBUG", "false")

    settings = Settings()

    assert settings.allowed_hosts == ["app.example.com", "127.0.0.1"]


def test_upload_retention_reads_hours_from_env(monkeypatch) -> None:
    monkeypatch.setenv("BOOKER_TEE_UPLOAD_RETENTION_HOURS", "72")

    assert Settings().upload_retention_hours == 72


async def test_lifespan_bounds_sidecar_ping_that_never_responds(monkeypatch) -> None:
    class HangingParser:
        async def ping(self) -> None:
            await asyncio.Event().wait()

    settings = Settings(
        statement_parser_socket_path=Path("/tmp/test-parser.sock"),
        statement_parser_startup_timeout_seconds=1,
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.main.StatementParserSidecarClient.from_settings",
        lambda _settings: HangingParser(),
    )
    started_at = monotonic()

    with pytest.raises(TimeoutError):
        async with lifespan(FastAPI()):
            pass

    assert monotonic() - started_at < 1.25


def test_trusted_host_blocks_unknown_host(client: TestClient) -> None:
    response = client.get("/health", headers={"host": "evil.example"})

    assert response.status_code == 400


def test_secure_cookie_settings_enable_hsts(monkeypatch) -> None:
    strong_secret = "production-secret-value-with-enough-entropy"
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(
            auth_secret_key=strong_secret,
            session_cookie_secure=True,
            allowed_hosts=["testserver"],
        ),
    )

    with TestClient(create_app()) as secure_client:
        response = secure_client.get("/health")

    assert response.headers["Strict-Transport-Security"] == ("max-age=31536000; includeSubDomains")


@pytest.mark.parametrize(
    ("settings", "expected_setting"),
    [
        pytest.param(
            Settings(environment="production", session_cookie_secure=True),
            "BOOKER_TEE_AUTH_SECRET_KEY",
            id="local-auth-secret",
        ),
        pytest.param(
            Settings(
                environment="production",
                auth_secret_key="production-secret-value-with-enough-entropy",
                session_cookie_secure=False,
            ),
            "BOOKER_TEE_SESSION_COOKIE_SECURE",
            id="insecure-session-cookie",
        ),
        pytest.param(
            Settings(
                environment="production",
                auth_secret_key="production-secret-value-with-enough-entropy",
                session_cookie_secure=True,
                allowed_hosts=["*"],
            ),
            "BOOKER_TEE_ALLOWED_HOSTS",
            id="wildcard-allowed-hosts",
        ),
        pytest.param(
            Settings(
                environment="production",
                registration_mode="closed",
                auth_secret_key="production-secret-value-with-enough-entropy",
                session_cookie_secure=True,
                allowed_hosts=["booker.example"],
                chat_integrations_enabled=True,
                telegram_mode="webhook",
                telegram_bot_token="bot-token",
                telegram_webhook_secret="too-short",
                public_base_url="https://booker.example",
            ),
            "BOOKER_TEE_TELEGRAM_WEBHOOK_SECRET",
            id="weak-telegram-webhook-secret",
        ),
    ],
)
def test_production_settings_reject_unsafe_values(
    settings: Settings,
    expected_setting: str,
) -> None:
    with pytest.raises(RuntimeError, match=expected_setting):
        settings.validate_for_runtime()
