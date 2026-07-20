import hashlib
import json
from decimal import Decimal

from app.features.ledger.application.commands import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
)


def manual_income_expense_fingerprint(command: CreateManualIncomeExpenseCommand) -> str:
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


def manual_transfer_fingerprint(command: CreateManualTransferCommand) -> str:
    return _fingerprint(
        {
            "operation_type": "transfer",
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
