import sys
from collections import defaultdict
from urllib.parse import urlsplit

from pydantic import ValidationError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.core.settings import LOCAL_AUTH_SECRET, Settings

PLACEHOLDER_SECRETS = frozenset(
    {
        "booker_tee",
        "booker-tee",
        "changeme",
        "change-me",
        "default",
        "password",
        "secret",
        "smtp-password",
        "telegram-bot-token",
        "telegram-webhook-secret",
    }
)


def validate_production_preflight(settings: Settings) -> list[str]:
    errors: list[str] = []
    try:
        settings.validate_for_runtime()
    except RuntimeError as error:
        errors.append(str(error))

    if settings.environment != "production":
        errors.append("BOOKER_TEE_ENVIRONMENT must be production.")
    if settings.debug:
        errors.append("BOOKER_TEE_DEBUG must be false.")
    if settings.registration_mode != "invite_only":
        errors.append("BOOKER_TEE_REGISTRATION_MODE must be invite_only.")
    if not settings.security_headers_enabled:
        errors.append("BOOKER_TEE_SECURITY_HEADERS_ENABLED must be true.")

    errors.extend(_validate_canonical_url(settings))
    errors.extend(_validate_email(settings))
    errors.extend(_validate_telegram(settings))
    database_password, database_errors = _validate_database_url(settings.database_url)
    errors.extend(database_errors)
    errors.extend(_validate_secrets(settings, database_password))
    return errors


def _validate_canonical_url(settings: Settings) -> list[str]:
    domain = (settings.domain or "").strip().casefold().rstrip(".")
    if not domain:
        return ["BOOKER_TEE_DOMAIN must be set."]

    errors: list[str] = []
    allowed_hosts = {host.casefold().rstrip(".") for host in settings.allowed_hosts}
    if domain not in allowed_hosts:
        errors.append("BOOKER_TEE_ALLOWED_HOSTS must contain BOOKER_TEE_DOMAIN.")

    try:
        public_url = urlsplit(settings.public_base_url or "")
        valid_url = (
            public_url.scheme == "https"
            and public_url.hostname is not None
            and public_url.hostname.casefold().rstrip(".") == domain
            and public_url.port is None
            and public_url.username is None
            and public_url.password is None
            and public_url.path in {"", "/"}
            and not public_url.query
            and not public_url.fragment
        )
    except ValueError:
        valid_url = False
    if not valid_url:
        errors.append("BOOKER_TEE_PUBLIC_BASE_URL must be the HTTPS origin for BOOKER_TEE_DOMAIN.")
    return errors


def _validate_email(settings: Settings) -> list[str]:
    errors: list[str] = []
    if not settings.identity_email_enabled:
        errors.append("BOOKER_TEE_IDENTITY_EMAIL_ENABLED must be true.")
    if settings.identity_email_from is None:
        errors.append("BOOKER_TEE_IDENTITY_EMAIL_FROM must be set.")
    if settings.smtp_host is None:
        errors.append("BOOKER_TEE_SMTP_HOST must be set.")
    if settings.smtp_username is None:
        errors.append("BOOKER_TEE_SMTP_USERNAME must be set.")
    if settings.smtp_password is None:
        errors.append("BOOKER_TEE_SMTP_PASSWORD must be set.")
    if not settings.smtp_starttls:
        errors.append("BOOKER_TEE_SMTP_STARTTLS must be true.")
    if not 1 <= settings.smtp_port <= 65535:
        errors.append("BOOKER_TEE_SMTP_PORT must be between 1 and 65535.")
    return errors


def _validate_telegram(settings: Settings) -> list[str]:
    errors: list[str] = []
    if not settings.chat_integrations_enabled:
        errors.append("BOOKER_TEE_CHAT_INTEGRATIONS_ENABLED must be true.")
    if settings.telegram_mode != "webhook":
        errors.append("BOOKER_TEE_TELEGRAM_MODE must be webhook.")
    if settings.telegram_bot_token is None:
        errors.append("BOOKER_TEE_TELEGRAM_BOT_TOKEN must be set.")
    if settings.telegram_webhook_secret is None:
        errors.append("BOOKER_TEE_TELEGRAM_WEBHOOK_SECRET must be set.")
    return errors


def _validate_database_url(database_url: str) -> tuple[str | None, list[str]]:
    try:
        parsed_url = make_url(database_url)
    except ArgumentError:
        return None, ["DATABASE_URL must be a valid PostgreSQL async URL."]

    errors: list[str] = []
    if parsed_url.drivername != "postgresql+asyncpg":
        errors.append("DATABASE_URL must use postgresql+asyncpg.")
    if parsed_url.host != "postgres":
        errors.append("DATABASE_URL must use the Compose host postgres.")
    if not parsed_url.username or not parsed_url.password or not parsed_url.database:
        errors.append("DATABASE_URL must include database name, username, and password.")
    return parsed_url.password, errors


def _validate_secrets(settings: Settings, database_password: str | None) -> list[str]:
    secrets = {
        "BOOKER_TEE_AUTH_SECRET_KEY": settings.auth_secret_key,
        "BOOKER_TEE_SMTP_PASSWORD": settings.smtp_password,
        "BOOKER_TEE_TELEGRAM_BOT_TOKEN": settings.telegram_bot_token,
        "BOOKER_TEE_TELEGRAM_WEBHOOK_SECRET": settings.telegram_webhook_secret,
        "DATABASE_URL password": database_password,
    }
    errors: list[str] = []
    for name, value in secrets.items():
        if value is not None and _is_placeholder_secret(value):
            errors.append(f"{name} must not use a default or placeholder value.")

    if settings.smtp_password is not None and len(settings.smtp_password) < 16:
        errors.append("BOOKER_TEE_SMTP_PASSWORD must contain at least 16 characters.")
    if database_password is not None and len(database_password) < 16:
        errors.append("DATABASE_URL password must contain at least 16 characters.")
    if settings.telegram_bot_token is not None and len(settings.telegram_bot_token) < 20:
        errors.append("BOOKER_TEE_TELEGRAM_BOT_TOKEN is too short.")
    for previous_secret in settings.auth_previous_secret_keys:
        if len(previous_secret) < 32 or _is_placeholder_secret(previous_secret):
            errors.append("BOOKER_TEE_AUTH_PREVIOUS_SECRET_KEYS must contain only strong secrets.")
            break

    names_by_secret: defaultdict[str, list[str]] = defaultdict(list)
    for name, value in secrets.items():
        if value:
            names_by_secret[value].append(name)
    for names in names_by_secret.values():
        if len(names) > 1:
            errors.append(f"{', '.join(names)} must use different secrets.")
    if settings.auth_secret_key in settings.auth_previous_secret_keys:
        errors.append(
            "BOOKER_TEE_AUTH_SECRET_KEY must differ from BOOKER_TEE_AUTH_PREVIOUS_SECRET_KEYS."
        )
    return errors


def _is_placeholder_secret(value: str) -> bool:
    normalized = value.strip().casefold()
    return normalized == LOCAL_AUTH_SECRET or normalized in PLACEHOLDER_SECRETS


def validation_error_fields(error: ValidationError) -> list[str]:
    fields: set[str] = set()
    for issue in error.errors(include_input=False, include_url=False):
        field_name = str(issue["loc"][0])
        model_field = Settings.model_fields.get(field_name)
        alias = model_field.validation_alias if model_field is not None else None
        fields.add(str(alias or field_name))
    return sorted(fields)


def main() -> None:
    try:
        settings = Settings()
    except ValidationError as error:
        print("Production preflight failed:", file=sys.stderr)
        for field in validation_error_fields(error):
            print(f"- {field} has an invalid value.", file=sys.stderr)
        raise SystemExit(1) from None

    errors = validate_production_preflight(settings)
    if errors:
        print("Production preflight failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)
    print("Production preflight passed.")


if __name__ == "__main__":
    main()
