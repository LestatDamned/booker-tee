from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

LOCAL_AUTH_SECRET = "change-this-local-auth-secret"


class Settings(BaseSettings):
    app_name: str = Field(default="Booker Tee", validation_alias="BOOKER_TEE_APP_NAME")
    environment: Literal["local", "test", "production"] = Field(
        default="local",
        validation_alias="BOOKER_TEE_ENVIRONMENT",
    )
    debug: bool = Field(default=False, validation_alias="BOOKER_TEE_DEBUG")
    allow_signups: bool = Field(default=True, validation_alias="BOOKER_TEE_ALLOW_SIGNUPS")
    auth_secret_key: str = Field(
        default=LOCAL_AUTH_SECRET,
        validation_alias="BOOKER_TEE_AUTH_SECRET_KEY",
    )
    session_cookie_name: str = Field(
        default="booker_session",
        validation_alias="BOOKER_TEE_SESSION_COOKIE_NAME",
    )
    session_cookie_secure: bool = Field(
        default=False,
        validation_alias="BOOKER_TEE_SESSION_COOKIE_SECURE",
    )
    session_max_age_seconds: int = Field(
        default=60 * 60 * 24 * 14,
        validation_alias="BOOKER_TEE_SESSION_MAX_AGE_SECONDS",
    )
    allowed_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["127.0.0.1", "localhost", "testserver"],
        validation_alias="BOOKER_TEE_ALLOWED_HOSTS",
    )
    security_headers_enabled: bool = Field(
        default=True,
        validation_alias="BOOKER_TEE_SECURITY_HEADERS_ENABLED",
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
    public_base_url: str | None = Field(
        default=None,
        validation_alias="BOOKER_TEE_PUBLIC_BASE_URL",
    )
    upload_storage_dir: Path = Field(
        default=Path("var/uploads"),
        validation_alias="BOOKER_TEE_UPLOAD_STORAGE_DIR",
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

    @field_validator(
        "telegram_bot_token",
        "telegram_webhook_secret",
        "public_base_url",
        mode="before",
    )
    @classmethod
    def empty_string_as_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

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
        if self.chat_integrations_enabled and self.telegram_bot_token is None:
            errors.append("BOOKER_TEE_TELEGRAM_BOT_TOKEN must be set when chat integrations run.")
        if self.chat_integrations_enabled and self.telegram_mode == "webhook":
            if self.public_base_url is None:
                errors.append("BOOKER_TEE_PUBLIC_BASE_URL must be set for Telegram webhook mode.")
            if self.telegram_webhook_secret is None:
                errors.append(
                    "BOOKER_TEE_TELEGRAM_WEBHOOK_SECRET must be set for Telegram webhook mode."
                )

        if errors:
            raise RuntimeError("Invalid production settings: " + " ".join(errors))
