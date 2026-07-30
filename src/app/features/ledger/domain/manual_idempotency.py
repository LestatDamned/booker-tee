import hashlib
import json
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.features.ledger.domain.types import OperationType


class ManualIncomeExpenseFingerprintInput(Protocol):
    operation_type: OperationType
    account_id: UUID
    amount: Decimal
    operation_date: date
    description: str | None
    category_id: UUID | None
    property_id: UUID | None


class ManualTransferFingerprintInput(Protocol):
    source_account_id: UUID
    destination_account_id: UUID
    amount: Decimal
    operation_date: date
    description: str | None


class ManualOperationFingerprint:
    @staticmethod
    def calculate_income_expense(command: ManualIncomeExpenseFingerprintInput) -> str:
        return _fingerprint(
            {
                "operation_type": command.operation_type.value,
                "account_id": str(command.account_id),
                "amount": _canonical_decimal(command.amount),
                "operation_date": command.operation_date.isoformat(),
                "description": command.description,
                "category_id": str(command.category_id) if command.category_id else None,
                "property_id": str(command.property_id) if command.property_id else None,
            }
        )

    @staticmethod
    def calculate_transfer(command: ManualTransferFingerprintInput) -> str:
        return _fingerprint(
            {
                "operation_type": OperationType.TRANSFER.value,
                "source_account_id": str(command.source_account_id),
                "destination_account_id": str(command.destination_account_id),
                "amount": _canonical_decimal(command.amount),
                "operation_date": command.operation_date.isoformat(),
                "description": command.description,
            }
        )


def _fingerprint(payload: dict[str, str | None]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def _canonical_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")
