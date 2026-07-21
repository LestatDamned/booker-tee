from app.features.accounts.models import Account
from app.features.categories.models import Category
from app.features.ledger.application.manual_operation_dtos import (
    AccountReferenceReadDto,
    ManualOperationMoneyReadDto,
    ManualOperationReadDto,
    NamedReferenceReadDto,
)
from app.features.ledger.models import MoneyEntry, Operation, OperationType
from app.features.properties.models import Property


class ManualOperationReadDtoMapper:
    @staticmethod
    def from_model(operation: Operation) -> ManualOperationReadDto:
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
            money=ManualOperationReadDtoMapper._money(money_entry),
            account=(
                ManualOperationReadDtoMapper._account(primary_entry.account)
                if primary_entry is not None and operation.type != OperationType.TRANSFER
                else None
            ),
            source_account=(
                ManualOperationReadDtoMapper._account(source_entry.account)
                if source_entry is not None
                else None
            ),
            destination_account=(
                ManualOperationReadDtoMapper._account(destination_entry.account)
                if destination_entry is not None
                else None
            ),
            category=ManualOperationReadDtoMapper._named_reference(operation.category),
            property=ManualOperationReadDtoMapper._named_reference(operation.property),
        )

    @staticmethod
    def _money(entry: MoneyEntry | None) -> ManualOperationMoneyReadDto | None:
        if entry is None:
            return None
        return ManualOperationMoneyReadDto(
            amount=abs(entry.amount),
            currency=entry.currency,
        )

    @staticmethod
    def _account(account: Account | None) -> AccountReferenceReadDto | None:
        if account is None:
            return None
        return AccountReferenceReadDto(
            id=account.id,
            name=account.name,
            currency=account.currency,
        )

    @staticmethod
    def _named_reference(
        reference: Category | Property | None,
    ) -> NamedReferenceReadDto | None:
        if reference is None:
            return None
        return NamedReferenceReadDto(id=reference.id, name=reference.name)
