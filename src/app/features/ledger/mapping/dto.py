from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.features.accounts.models import Account, AccountType
from app.features.categories.models import Category, CategoryKind
from app.features.ledger.models import MoneyEntry, Operation, OperationStatus, OperationType
from app.features.properties.models import Property


@dataclass(frozen=True)
class AccountView:
    id: UUID
    name: str
    type: AccountType
    currency: str
    is_active: bool
    initial_balance: Decimal


@dataclass(frozen=True)
class CategoryView:
    id: UUID
    name: str
    kind: CategoryKind


@dataclass(frozen=True)
class PropertyView:
    id: UUID
    name: str


@dataclass(frozen=True)
class OperationRefMoneyEntryView:
    account_id: UUID
    account: AccountView | None
    amount: Decimal


@dataclass(frozen=True)
class OperationRefView:
    id: UUID
    type: OperationType
    status: OperationStatus
    operation_date: date
    description: str | None
    category: CategoryView | None
    property: PropertyView | None
    money_entries: list[OperationRefMoneyEntryView]


@dataclass(frozen=True)
class AccountLedgerEntryView:
    operation: OperationRefView
    operation_id: UUID
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class AccountLedgerDetailView:
    account: AccountView
    balance: Decimal
    entries: list[AccountLedgerEntryView]


@dataclass(frozen=True)
class ManualOperationView:
    id: UUID
    type: OperationType
    status: OperationStatus
    operation_date: date
    description: str | None
    category_id: UUID | None
    property_id: UUID | None
    category: CategoryView | None
    property: PropertyView | None
    primary_entry: OperationRefMoneyEntryView | None
    source_entry: OperationRefMoneyEntryView | None
    destination_entry: OperationRefMoneyEntryView | None
    edit_amount: Decimal | None


class LedgerViewMapper:
    @staticmethod
    def account_detail_from_parts(
        *,
        account: Account,
        balance: Decimal,
        entries: list[MoneyEntry],
    ) -> AccountLedgerDetailView:
        account_view = LedgerViewMapper.account_from_model(account)
        if account_view is None:
            raise ValueError("Account detail requires an account.")
        return AccountLedgerDetailView(
            account=account_view,
            balance=balance,
            entries=[LedgerViewMapper.account_entry_from_model(entry) for entry in entries],
        )

    @staticmethod
    def manual_operation_from_model(operation: Operation) -> ManualOperationView:
        entries = [
            LedgerViewMapper.operation_money_entry_from_model(entry)
            for entry in operation.money_entries
        ]
        primary_entry = first_entry(entries)
        source_entry = first_negative_entry(entries)
        destination_entry = first_positive_entry(entries)
        return ManualOperationView(
            id=operation.id,
            type=operation.type,
            status=operation.status,
            operation_date=operation.operation_date,
            description=operation.description,
            category_id=operation.category_id,
            property_id=operation.property_id,
            category=LedgerViewMapper.category_from_model(operation.category),
            property=LedgerViewMapper.property_from_model(operation.property),
            primary_entry=primary_entry,
            source_entry=source_entry,
            destination_entry=destination_entry,
            edit_amount=manual_operation_edit_amount(
                operation.type,
                primary_entry=primary_entry,
                destination_entry=destination_entry,
            ),
        )

    @staticmethod
    def account_entry_from_model(entry: MoneyEntry) -> AccountLedgerEntryView:
        return AccountLedgerEntryView(
            operation=LedgerViewMapper.operation_ref_from_model(entry.operation),
            operation_id=entry.operation_id,
            amount=entry.amount,
            currency=entry.currency,
        )

    @staticmethod
    def operation_ref_from_model(operation: Operation) -> OperationRefView:
        return OperationRefView(
            id=operation.id,
            type=operation.type,
            status=operation.status,
            operation_date=operation.operation_date,
            description=operation.description,
            category=LedgerViewMapper.category_from_model(operation.category),
            property=LedgerViewMapper.property_from_model(operation.property),
            money_entries=[
                LedgerViewMapper.operation_money_entry_from_model(entry)
                for entry in operation.money_entries
            ],
        )

    @staticmethod
    def operation_money_entry_from_model(entry: MoneyEntry) -> OperationRefMoneyEntryView:
        return OperationRefMoneyEntryView(
            account_id=entry.account_id,
            account=LedgerViewMapper.account_from_model(entry.account),
            amount=entry.amount,
        )

    @staticmethod
    def account_from_model(account: Account | None) -> AccountView | None:
        if account is None:
            return None
        return AccountView(
            id=account.id,
            name=account.name,
            type=account.type,
            currency=account.currency,
            is_active=account.is_active,
            initial_balance=account.initial_balance,
        )

    @staticmethod
    def category_from_model(category: Category | None) -> CategoryView | None:
        if category is None:
            return None
        return CategoryView(
            id=category.id,
            name=category.name,
            kind=category.kind,
        )

    @staticmethod
    def property_from_model(property_: Property | None) -> PropertyView | None:
        if property_ is None:
            return None
        return PropertyView(
            id=property_.id,
            name=property_.name,
        )


def first_entry(
    entries: list[OperationRefMoneyEntryView],
) -> OperationRefMoneyEntryView | None:
    return entries[0] if entries else None


def first_negative_entry(
    entries: list[OperationRefMoneyEntryView],
) -> OperationRefMoneyEntryView | None:
    return next((entry for entry in entries if entry.amount < 0), None)


def first_positive_entry(
    entries: list[OperationRefMoneyEntryView],
) -> OperationRefMoneyEntryView | None:
    return next((entry for entry in entries if entry.amount > 0), None)


def manual_operation_edit_amount(
    operation_type: OperationType,
    *,
    primary_entry: OperationRefMoneyEntryView | None,
    destination_entry: OperationRefMoneyEntryView | None,
) -> Decimal | None:
    if operation_type == OperationType.TRANSFER and destination_entry is not None:
        return destination_entry.amount
    if primary_entry is None:
        return None
    return abs(primary_entry.amount)
