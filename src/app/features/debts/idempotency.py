import hashlib
import json
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from app.shared.schemas import ApplicationModel


class DebtCommandFingerprint:
    @classmethod
    def calculate(cls, action: str, command: ApplicationModel) -> str:
        payload = {"action": action, **command.model_dump()}
        serialized = json.dumps(
            cls._canonical(payload),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode()).hexdigest()

    @classmethod
    def _canonical(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: cls._canonical(item) for key, item in value.items()}
        if isinstance(value, Decimal):
            return format(value.normalize(), "f")
        if isinstance(value, (date, UUID)):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        return value
