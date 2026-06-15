from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Booker Tee", validation_alias="BOOKER_TEE_APP_NAME")
    debug: bool = Field(default=False, validation_alias="BOOKER_TEE_DEBUG")
    dev_user_email: str = Field(
        default="dev@booker-tee.local",
        validation_alias="BOOKER_TEE_DEV_USER_EMAIL",
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
