from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Booker Tee", validation_alias="BOOKER_TEE_APP_NAME")
    debug: bool = Field(default=False, validation_alias="BOOKER_TEE_DEBUG")
    allow_signups: bool = Field(default=True, validation_alias="BOOKER_TEE_ALLOW_SIGNUPS")
    auth_secret_key: str = Field(
        default="change-this-local-auth-secret",
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
    )
