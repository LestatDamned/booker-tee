from typing import Literal

from pydantic import Field, field_validator

from app.api.schemas import ApiModel, ApiRequestModel


class TelegramDevLinkConfigApiResponse(ApiModel):
    enabled: Literal[True] = True


class BindTelegramDevLinkApiRequest(ApiRequestModel):
    external_user_id: str = Field(min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=255)

    @field_validator("external_user_id", mode="before")
    @classmethod
    def normalize_external_user_id(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class BindTelegramDevLinkApiResponse(ApiModel):
    bound: Literal[True] = True
