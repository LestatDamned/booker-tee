from datetime import date
from enum import StrEnum
from uuid import UUID

from fastapi import HTTPException, status


def parse_optional_query_uuid(raw_value: str | None, *, field_name: str) -> UUID | None:
    if not raw_value:
        return None
    try:
        return UUID(raw_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} должен быть валидным UUID.",
        ) from exc


def parse_optional_query_date(raw_value: str | None, *, field_name: str) -> date | None:
    if not raw_value:
        return None
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} должен быть датой в формате YYYY-MM-DD.",
        ) from exc


def parse_optional_query_enum[T: StrEnum](
    raw_value: str | None,
    enum_type: type[T],
    *,
    field_name: str,
) -> T | None:
    if not raw_value:
        return None
    try:
        return enum_type(raw_value)
    except ValueError as exc:
        allowed_values = ", ".join(item.value for item in enum_type)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} должен быть одним из: {allowed_values}.",
        ) from exc


def clean_optional_query_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None
