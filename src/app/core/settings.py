import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

LOCAL_AUTH_SECRET = "change-this-local-auth-secret"


class Settings(BaseSettings):
    app_name: str = Field(default="Booker Tee", validation_alias="BOOKER_TEE_APP_NAME")
    environment: Literal["local", "test", "production"] = Field(
        default="local",
        validation_alias="BOOKER_TEE_ENVIRONMENT",
    )
    debug: bool = Field(default=False, validation_alias="BOOKER_TEE_DEBUG")
    registration_mode: Literal["open", "invite_only", "closed"] = Field(
        default="open",
        validation_alias="BOOKER_TEE_REGISTRATION_MODE",
    )
    password_min_length: int = Field(
        default=8,
        ge=8,
        le=1024,
        validation_alias="BOOKER_TEE_PASSWORD_MIN_LENGTH",
    )
    auth_secret_key: str = Field(
        default=LOCAL_AUTH_SECRET,
        validation_alias="BOOKER_TEE_AUTH_SECRET_KEY",
    )
    auth_previous_secret_keys: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        validation_alias="BOOKER_TEE_AUTH_PREVIOUS_SECRET_KEYS",
    )
    refresh_cookie_name: str = Field(
        default="booker_refresh",
        validation_alias="BOOKER_TEE_REFRESH_COOKIE_NAME",
    )
    session_cookie_secure: bool = Field(
        default=False,
        validation_alias="BOOKER_TEE_SESSION_COOKIE_SECURE",
    )
    session_max_age_seconds: int = Field(
        default=60 * 60 * 24 * 14,
        ge=60,
        validation_alias="BOOKER_TEE_SESSION_MAX_AGE_SECONDS",
    )
    access_token_max_age_seconds: int = Field(
        default=15 * 60,
        ge=60,
        le=60 * 60,
        validation_alias="BOOKER_TEE_ACCESS_TOKEN_MAX_AGE_SECONDS",
    )
    refresh_reuse_grace_seconds: int = Field(
        default=10,
        ge=0,
        le=60,
        validation_alias="BOOKER_TEE_REFRESH_REUSE_GRACE_SECONDS",
    )
    session_idle_timeout_seconds: int = Field(
        default=60 * 60 * 12,
        ge=60,
        validation_alias="BOOKER_TEE_SESSION_IDLE_TIMEOUT_SECONDS",
    )
    session_touch_interval_seconds: int = Field(
        default=5 * 60,
        ge=1,
        validation_alias="BOOKER_TEE_SESSION_TOUCH_INTERVAL_SECONDS",
    )
    identity_email_enabled: bool = Field(
        default=False,
        validation_alias="BOOKER_TEE_IDENTITY_EMAIL_ENABLED",
    )
    identity_email_from: str | None = Field(
        default=None,
        validation_alias="BOOKER_TEE_IDENTITY_EMAIL_FROM",
    )
    smtp_host: str | None = Field(default=None, validation_alias="BOOKER_TEE_SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="BOOKER_TEE_SMTP_PORT")
    smtp_username: str | None = Field(
        default=None,
        validation_alias="BOOKER_TEE_SMTP_USERNAME",
    )
    smtp_password: str | None = Field(
        default=None,
        validation_alias="BOOKER_TEE_SMTP_PASSWORD",
    )
    smtp_starttls: bool = Field(
        default=True,
        validation_alias="BOOKER_TEE_SMTP_STARTTLS",
    )
    allowed_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["127.0.0.1", "localhost", "testserver"],
        validation_alias="BOOKER_TEE_ALLOWED_HOSTS",
    )
    security_headers_enabled: bool = Field(
        default=True,
        validation_alias="BOOKER_TEE_SECURITY_HEADERS_ENABLED",
    )
    domain: str | None = Field(
        default=None,
        validation_alias="BOOKER_TEE_DOMAIN",
    )
    chat_integrations_enabled: bool = Field(
        default=False,
        validation_alias="BOOKER_TEE_CHAT_INTEGRATIONS_ENABLED",
    )
    telegram_bot_token: str | None = Field(
        default=None,
        validation_alias="BOOKER_TEE_TELEGRAM_BOT_TOKEN",
    )
    telegram_mode: Literal["polling", "webhook"] = Field(
        default="polling",
        validation_alias="BOOKER_TEE_TELEGRAM_MODE",
    )
    telegram_webhook_secret: str | None = Field(
        default=None,
        validation_alias="BOOKER_TEE_TELEGRAM_WEBHOOK_SECRET",
    )
    telegram_polling_timeout_seconds: int = Field(
        default=30,
        validation_alias="BOOKER_TEE_TELEGRAM_POLLING_TIMEOUT_SECONDS",
    )
    telegram_proxy_url: AnyHttpUrl | None = Field(
        default=None,
        validation_alias="BOOKER_TEE_TELEGRAM_PROXY_URL",
    )
    public_base_url: str | None = Field(
        default=None,
        validation_alias="BOOKER_TEE_PUBLIC_BASE_URL",
    )
    upload_storage_dir: Path = Field(
        default=Path("var/uploads"),
        validation_alias="BOOKER_TEE_UPLOAD_STORAGE_DIR",
    )
    upload_retention_hours: int = Field(
        default=48,
        ge=1,
        validation_alias="BOOKER_TEE_UPLOAD_RETENTION_HOURS",
    )
    statement_upload_max_bytes: int = Field(
        default=20 * 1024 * 1024,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_UPLOAD_MAX_BYTES",
    )
    statement_pdf_max_pages: int = Field(
        default=200,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_PDF_MAX_PAGES",
    )
    statement_pdf_max_characters: int = Field(
        default=5_000_000,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_PDF_MAX_CHARACTERS",
    )
    statement_pdf_max_tables: int = Field(
        default=2_000,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_PDF_MAX_TABLES",
    )
    statement_pdf_max_cells: int = Field(
        default=500_000,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_PDF_MAX_CELLS",
    )
    statement_extraction_result_max_bytes: int = Field(
        default=64 * 1024 * 1024,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_EXTRACTION_RESULT_MAX_BYTES",
    )
    statement_parser_wall_timeout_seconds: int = Field(
        default=60,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_PARSER_WALL_TIMEOUT_SECONDS",
    )
    statement_parser_cpu_seconds: int = Field(
        default=45,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_PARSER_CPU_SECONDS",
    )
    statement_parser_memory_bytes: int = Field(
        default=512 * 1024 * 1024,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_PARSER_MEMORY_BYTES",
    )
    statement_parser_socket_path: Path | None = Field(
        default=None,
        validation_alias="BOOKER_TEE_STATEMENT_PARSER_SOCKET_PATH",
    )
    statement_parser_startup_timeout_seconds: int = Field(
        default=30,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_PARSER_STARTUP_TIMEOUT_SECONDS",
    )
    statement_xlsx_max_sheets: int = Field(
        default=20,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_XLSX_MAX_SHEETS",
    )
    statement_xlsx_max_rows_per_sheet: int = Field(
        default=50_000,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_XLSX_MAX_ROWS_PER_SHEET",
    )
    statement_xlsx_max_columns_per_sheet: int = Field(
        default=100,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_XLSX_MAX_COLUMNS_PER_SHEET",
    )
    statement_xlsx_max_cells: int = Field(
        default=1_000_000,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_XLSX_MAX_CELLS",
    )
    statement_xlsx_max_uncompressed_bytes: int = Field(
        default=100 * 1024 * 1024,
        ge=1,
        validation_alias="BOOKER_TEE_STATEMENT_XLSX_MAX_UNCOMPRESSED_BYTES",
    )
    database_url: str = Field(
        default="postgresql+asyncpg://booker_tee:booker_tee@localhost:5432/booker_tee",
        validation_alias="DATABASE_URL",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return [host.strip() for host in value.split(",") if host.strip()]
        return value

    @field_validator("auth_previous_secret_keys", mode="before")
    @classmethod
    def parse_previous_auth_secrets(cls, value: object) -> object:
        if isinstance(value, str):
            return [secret.strip() for secret in value.split(",") if secret.strip()]
        return value

    @field_validator(
        "telegram_bot_token",
        "telegram_webhook_secret",
        "telegram_proxy_url",
        "public_base_url",
        "domain",
        "identity_email_from",
        "smtp_host",
        "smtp_username",
        "smtp_password",
        mode="before",
    )
    @classmethod
    def empty_string_as_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_parser_limits(self) -> "Settings":
        if self.statement_parser_cpu_seconds > self.statement_parser_wall_timeout_seconds:
            raise ValueError("statement parser CPU limit cannot exceed wall timeout")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def session_cookie_name(self) -> str:
        """Compatibility for callers migrating to the scoped refresh cookie."""
        return self.refresh_cookie_name

    def validate_for_runtime(self) -> None:
        if not self.is_production:
            return

        errors: list[str] = []
        if self.auth_secret_key == LOCAL_AUTH_SECRET or len(self.auth_secret_key) < 32:
            errors.append("BOOKER_TEE_AUTH_SECRET_KEY must be set to a strong production secret.")
        if not self.session_cookie_secure:
            errors.append("BOOKER_TEE_SESSION_COOKIE_SECURE must be true in production.")
        if not self.allowed_hosts or "*" in self.allowed_hosts:
            errors.append("BOOKER_TEE_ALLOWED_HOSTS must list explicit production hosts.")
        if self.registration_mode != "closed" and not self.identity_email_enabled:
            errors.append(
                "BOOKER_TEE_IDENTITY_EMAIL_ENABLED must be true when production signups run."
            )
        if self.identity_email_enabled:
            if self.public_base_url is None or not self.public_base_url.startswith("https://"):
                errors.append(
                    "BOOKER_TEE_PUBLIC_BASE_URL must be an HTTPS URL when identity email runs."
                )
            if self.identity_email_from is None:
                errors.append(
                    "BOOKER_TEE_IDENTITY_EMAIL_FROM must be set when identity email runs."
                )
            if self.smtp_host is None:
                errors.append("BOOKER_TEE_SMTP_HOST must be set when identity email runs.")
            if (self.smtp_username is None) != (self.smtp_password is None):
                errors.append(
                    "BOOKER_TEE_SMTP_USERNAME and BOOKER_TEE_SMTP_PASSWORD must be set together."
                )
        if self.chat_integrations_enabled and self.telegram_bot_token is None:
            errors.append("BOOKER_TEE_TELEGRAM_BOT_TOKEN must be set when chat integrations run.")
        if self.chat_integrations_enabled and self.telegram_mode == "webhook":
            if self.public_base_url is None:
                errors.append("BOOKER_TEE_PUBLIC_BASE_URL must be set for Telegram webhook mode.")
            if self.telegram_webhook_secret is None:
                errors.append(
                    "BOOKER_TEE_TELEGRAM_WEBHOOK_SECRET must be set for Telegram webhook mode."
                )
            elif (
                len(self.telegram_webhook_secret) < 32
                or len(self.telegram_webhook_secret) > 256
                or re.fullmatch(r"[A-Za-z0-9_-]+", self.telegram_webhook_secret) is None
            ):
                errors.append(
                    "BOOKER_TEE_TELEGRAM_WEBHOOK_SECRET must contain 32-256 characters "
                    "using only A-Z, a-z, 0-9, underscore, or hyphen."
                )

        if errors:
            raise RuntimeError("Invalid production settings: " + " ".join(errors))
