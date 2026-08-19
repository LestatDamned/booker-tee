from pathlib import Path
from subprocess import run

import pytest
from pydantic import ValidationError

from app.core.production_preflight import (
    validate_production_preflight,
    validation_error_fields,
)
from app.core.settings import Settings

PROJECT_ROOT = Path(__file__).parents[2]


def production_settings(**updates: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "debug": False,
        "registration_mode": "invite_only",
        "auth_secret_key": "auth-secret-value-with-at-least-32-characters",
        "session_cookie_secure": True,
        "allowed_hosts": ["finance.example.com"],
        "security_headers_enabled": True,
        "domain": "finance.example.com",
        "identity_email_enabled": True,
        "identity_email_from": "Booker Tee <booker@example.com>",
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_username": "booker@example.com",
        "smtp_password": "smtp-secret-value-12345",
        "smtp_starttls": True,
        "chat_integrations_enabled": True,
        "telegram_bot_token": "123456789:telegram-token-value-abcdef",
        "telegram_mode": "webhook",
        "telegram_webhook_secret": "telegram_webhook_secret_value_123456",
        "public_base_url": "https://finance.example.com",
        "database_url": (
            "postgresql+asyncpg://booker_tee:database-secret-value-123@postgres:5432/booker_tee"
        ),
    }
    values.update(updates)
    return Settings.model_validate(values)


def test_production_preflight_accepts_consistent_settings() -> None:
    assert validate_production_preflight(production_settings()) == []


@pytest.mark.parametrize(
    ("updates", "expected_error"),
    [
        ({"environment": "local"}, "BOOKER_TEE_ENVIRONMENT"),
        ({"debug": True}, "BOOKER_TEE_DEBUG"),
        ({"registration_mode": "open"}, "BOOKER_TEE_REGISTRATION_MODE"),
        ({"security_headers_enabled": False}, "BOOKER_TEE_SECURITY_HEADERS_ENABLED"),
        ({"domain": "other.example.com"}, "BOOKER_TEE_ALLOWED_HOSTS"),
        ({"public_base_url": "http://finance.example.com"}, "BOOKER_TEE_PUBLIC_BASE_URL"),
        ({"identity_email_enabled": False}, "BOOKER_TEE_IDENTITY_EMAIL_ENABLED"),
        ({"smtp_starttls": False}, "BOOKER_TEE_SMTP_STARTTLS"),
        ({"smtp_username": None}, "BOOKER_TEE_SMTP_USERNAME"),
        ({"chat_integrations_enabled": False}, "BOOKER_TEE_CHAT_INTEGRATIONS_ENABLED"),
        ({"telegram_mode": "polling"}, "BOOKER_TEE_TELEGRAM_MODE"),
        (
            {
                "database_url": (
                    "postgresql+asyncpg://booker_tee:database-secret-value-123@"
                    "localhost:5432/booker_tee"
                )
            },
            "Compose host postgres",
        ),
        (
            {
                "database_url": (
                    "postgresql+asyncpg://booker_tee:booker_tee@postgres:5432/booker_tee"
                )
            },
            "DATABASE_URL password",
        ),
        (
            {"smtp_password": "auth-secret-value-with-at-least-32-characters"},
            "must use different secrets",
        ),
    ],
)
def test_production_preflight_rejects_unsafe_setting_groups(
    updates: dict[str, object],
    expected_error: str,
) -> None:
    errors = validate_production_preflight(production_settings(**updates))

    assert expected_error in " ".join(errors)


def test_settings_validation_errors_expose_field_name_without_input_value() -> None:
    secret_invalid_value = "secret-invalid-port-value"
    with pytest.raises(ValidationError) as caught:
        production_settings(smtp_port=secret_invalid_value)

    fields = validation_error_fields(caught.value)

    assert fields == ["BOOKER_TEE_SMTP_PORT"]
    assert secret_invalid_value not in repr(fields)


def test_host_preflight_rejects_git_tracked_env_file() -> None:
    result = run(
        [str(PROJECT_ROOT / "scripts/production-preflight.sh")],
        cwd=PROJECT_ROOT,
        env={"BOOKER_TEE_ENV_FILE": str(PROJECT_ROOT / ".env.example"), "PATH": "/usr/bin"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "tracked by Git" in result.stderr


def test_host_preflight_rejects_broad_env_permissions(tmp_path: Path) -> None:
    env_file = tmp_path / "production.env"
    env_file.write_text("BOOKER_TEE_ENVIRONMENT=production\n")
    env_file.chmod(0o640)

    result = run(
        [str(PROJECT_ROOT / "scripts/production-preflight.sh")],
        cwd=PROJECT_ROOT,
        env={"BOOKER_TEE_ENV_FILE": str(env_file), "PATH": "/usr/bin"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "permissions must be 600" in result.stderr


def test_host_preflight_runs_container_for_private_untracked_env(tmp_path: Path) -> None:
    env_file = tmp_path / "production.env"
    env_file.write_text("BOOKER_TEE_ENVIRONMENT=production\n")
    env_file.chmod(0o600)
    executable_dir = tmp_path / "bin"
    executable_dir.mkdir()
    docker = executable_dir / "docker"
    docker.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\"\n")
    docker.chmod(0o700)

    result = run(
        [str(PROJECT_ROOT / "scripts/production-preflight.sh")],
        cwd=PROJECT_ROOT,
        env={
            "BOOKER_TEE_ENV_FILE": str(env_file),
            "PATH": f"{executable_dir}:/usr/bin",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "run --rm --no-deps app python -m app.core.production_preflight" in result.stdout
