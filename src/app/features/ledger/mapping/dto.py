from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.features.accounts.models import Account, AccountType
from app.features.categories.models import Category, CategoryKind
from app.features.imports.models import RawTransaction
from app.features.ledger.application.listing import LedgerPage
from app.features.ledger.models import (
    MoneyEntry,
    Operation,
    OperationSource,
    OperationStatus,
    OperationType,
)
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
class RawTransactionLinkView:
    id: UUID
    uploaded_document_id: UUID


@dataclass(frozen=True)
class OperationRefView:
    id: UUID
    type: OperationType
    status: OperationStatus
    source: OperationSource
    operation_date: date
    description: str | None
    category: CategoryView | None
    property: PropertyView | None
    money_entries: list[OperationRefMoneyEntryView]
    raw_transactions: list[RawTransactionLinkView]


@dataclass(frozen=True)
class AccountLedgerEntryView:
    operation: OperationRefView
    operation_id: UUID
    amount: Decimal
    currency: str

    @property
    def amount_direction(self) -> str:
        if self.operation.type == OperationType.TRANSFER:
            return "transfer"
        if self.amount > 0:
            return "income"
        if self.amount < 0:
            return "expense"
        return "transfer"


@dataclass(frozen=True)
class AccountLedgerDetailView:
    account: AccountView
    balance: Decimal
    entries: list[AccountLedgerEntryView]
    page: LedgerPage


class LedgerViewMapper:
    @staticmethod
    def account_detail_from_parts(
        *,
        account: Account,
        balance: Decimal,
        entries: list[MoneyEntry],
        page: LedgerPage,
    ) -> AccountLedgerDetailView:
        account_view = LedgerViewMapper.account_from_model(account)
        if account_view is None:
            raise ValueError("Account detail requires an account.")
        return AccountLedgerDetailView(
            account=account_view,
            balance=balance,
            entries=[LedgerViewMapper.account_entry_from_model(entry) for entry in entries],
            page=page,
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
            source=operation.source,
            operation_date=operation.operation_date,
            description=operation.description,
            category=LedgerViewMapper.category_from_model(operation.category),
            property=LedgerViewMapper.property_from_model(operation.property),
            money_entries=[
                LedgerViewMapper.operation_money_entry_from_model(entry)
                for entry in operation.money_entries
            ],
            raw_transactions=[
                LedgerViewMapper.raw_transaction_link_from_model(row)
                for row in operation.raw_transactions
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

    @staticmethod
    def raw_transaction_link_from_model(raw_transaction: RawTransaction) -> RawTransactionLinkView:
        return RawTransactionLinkView(
            id=raw_transaction.id,
            uploaded_document_id=raw_transaction.uploaded_document_id,
        )
