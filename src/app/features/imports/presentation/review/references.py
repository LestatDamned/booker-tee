from collections.abc import Sequence
from enum import Enum
from uuid import UUID


class ReviewReferenceResolver:
    @staticmethod
    def enum_or_none[EnumT: Enum](enum_type: type[EnumT], value: object) -> EnumT | None:
        if value is None:
            return None
        if isinstance(value, enum_type):
            return value
        raw_value = getattr(value, "value", value)
        try:
            return enum_type(raw_value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def required_id(value: object) -> UUID:
        object_id = getattr(value, "id", None)
        if not isinstance(object_id, UUID):
            raise ValueError("Expected object with UUID id.")
        return object_id

    @staticmethod
    def source_account_id(row: object, document: object) -> UUID | None:
        return (
            getattr(row, "source_account_id", None)
            or getattr(row, "account_id", None)
            or getattr(
                document,
                "account_id",
                None,
            )
        )

    @staticmethod
    def counterparty_account_id(row: object) -> UUID | None:
        raw_value = getattr(row, "counterparty_account_id", None)
        if raw_value is not None:
            return raw_value
        raw_payload = getattr(row, "raw_payload", None)
        if not isinstance(raw_payload, dict):
            return None
        value = raw_payload.get("counterparty_account_id")
        return value if isinstance(value, UUID) else None

    @staticmethod
    def category_by_id(categories: Sequence[object], category_id: UUID | None) -> object | None:
        return ReviewReferenceResolver.object_by_id(categories, category_id)

    @staticmethod
    def object_by_id(objects: Sequence[object], object_id: UUID | None) -> object | None:
        if object_id is None:
            return None
        return next((item for item in objects if getattr(item, "id", None) == object_id), None)
