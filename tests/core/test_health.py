from api_client import ApiTestClient as TestClient
from app.core.settings import Settings
from app.main import create_app


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


def test_production_settings_reject_local_secret() -> None:
    settings = Settings(environment="production", session_cookie_secure=True)

    try:
        settings.validate_for_runtime()
    except RuntimeError as exc:
        assert "BOOKER_TEE_AUTH_SECRET_KEY" in str(exc)
    else:
        raise AssertionError("production settings accepted the local auth secret")


def test_production_settings_reject_insecure_cookie() -> None:
    settings = Settings(
        environment="production",
        auth_secret_key="production-secret-value-with-enough-entropy",
        session_cookie_secure=False,
    )

    try:
        settings.validate_for_runtime()
    except RuntimeError as exc:
        assert "BOOKER_TEE_SESSION_COOKIE_SECURE" in str(exc)
    else:
        raise AssertionError("production settings accepted insecure cookies")


def test_production_settings_reject_wildcard_hosts() -> None:
    settings = Settings(
        environment="production",
        auth_secret_key="production-secret-value-with-enough-entropy",
        session_cookie_secure=True,
        allowed_hosts=["*"],
    )

    try:
        settings.validate_for_runtime()
    except RuntimeError as exc:
        assert "BOOKER_TEE_ALLOWED_HOSTS" in str(exc)
    else:
        raise AssertionError("production settings accepted wildcard hosts")


def test_production_settings_reject_weak_telegram_webhook_secret() -> None:
    settings = Settings(
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
    )

    try:
        settings.validate_for_runtime()
    except RuntimeError as exc:
        assert "BOOKER_TEE_TELEGRAM_WEBHOOK_SECRET" in str(exc)
    else:
        raise AssertionError("production settings accepted a weak Telegram webhook secret")
