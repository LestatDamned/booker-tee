"""Shared configuration for internal application data models."""

from pydantic import BaseModel, ConfigDict


class ApplicationModel(BaseModel):
    """Immutable validated data passed between application boundaries."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        frozen=True,
    )
