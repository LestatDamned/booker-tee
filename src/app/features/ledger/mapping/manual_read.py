from app.features.ledger.models import MoneyEntry, Operation, OperationType
from app.features.ledger.schemas.manual import (
    AccountReferenceReadDto,
    ManualOperationMoneyReadDto,
    ManualOperationReadDto,
    NamedReferenceReadDto,
)


class ManualOperationReadMapper:
    @staticmethod
    def from_operation(operation: Operation) -> ManualOperationReadDto:
        primary_entry = operation.money_entries[0] if operation.money_entries else None
        source_entry = next((entry for entry in operation.money_entries if entry.amount < 0), None)
        destination_entry = next(
            (entry for entry in operation.money_entries if entry.amount > 0),
            None,
        )
        money_entry = source_entry if operation.type == OperationType.TRANSFER else primary_entry
        return ManualOperationReadDto(
            id=operation.id,
            version=operation.version,
            operation_type=operation.type,
            status=operation.status,
            operation_date=operation.operation_date,
            description=operation.description,
            money=ManualOperationReadMapper._money(money_entry),
            account=(
                AccountReferenceReadDto.model_validate(primary_entry.account)
                if primary_entry is not None and operation.type != OperationType.TRANSFER
                else None
            ),
            source_account=(
                AccountReferenceReadDto.model_validate(source_entry.account)
                if source_entry is not None
                else None
            ),
            destination_account=(
                AccountReferenceReadDto.model_validate(destination_entry.account)
                if destination_entry is not None
                else None
            ),
            category=(
                NamedReferenceReadDto.model_validate(operation.category)
                if operation.category is not None
                else None
            ),
            property=(
                NamedReferenceReadDto.model_validate(operation.property)
                if operation.property is not None
                else None
            ),
        )

    @staticmethod
    def _money(entry: MoneyEntry | None) -> ManualOperationMoneyReadDto | None:
        if entry is None:
            return None
        return ManualOperationMoneyReadDto(
            amount=abs(entry.amount),
            currency=entry.currency,
        )
