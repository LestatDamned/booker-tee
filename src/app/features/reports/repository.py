from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account
from app.features.categories.models import Category
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.models import UploadedDocument
from app.features.ledger.domain.types import OperationStatus
from app.features.ledger.models import MoneyEntry, Operation
from app.features.properties.models import Property, PropertyStatus

if TYPE_CHECKING:
    from app.features.reports.application.overview import ReportingFilters

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class ReportFilterAccountRow:
    id: UUID
    name: str
    currency: str
    is_active: bool


@dataclass(frozen=True)
class ReportFilterCategoryRow:
    id: UUID
    name: str
    is_active: bool


@dataclass(frozen=True)
class ReportFilterPropertyRow:
    id: UUID
    name: str
    is_active: bool


@dataclass(frozen=True)
class ReportMoneySummaryRow:
    currency: str
    income: Decimal
    expense: Decimal
    profit: Decimal


@dataclass(frozen=True)
class ReportAccountBalanceRow:
    account_id: UUID
    name: str
    currency: str
    balance: Decimal
    is_active: bool


@dataclass(frozen=True)
class ReportCategoryAggregateRow:
    category_id: UUID | None
    name: str
    currency: str
    income: Decimal
    expense: Decimal
    profit: Decimal
    is_active: bool


@dataclass(frozen=True)
class ReportPropertyAggregateRow:
    property_id: UUID
    name: str
    currency: str
    income: Decimal
    expense: Decimal
    profit: Decimal
    is_active: bool


class ReportsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_filter_accounts(self, workspace_id: UUID) -> list[ReportFilterAccountRow]:
        result = await self.session.execute(
            select(Account.id, Account.name, Account.currency, Account.is_active)
            .where(Account.workspace_id == workspace_id)
            .order_by(Account.is_active.desc(), Account.name, Account.id)
        )
        return [ReportFilterAccountRow(*row) for row in result.tuples().all()]

    async def list_filter_categories(self, workspace_id: UUID) -> list[ReportFilterCategoryRow]:
        result = await self.session.execute(
            select(Category.id, Category.name, Category.is_active)
            .where(Category.workspace_id == workspace_id)
            .order_by(Category.is_active.desc(), Category.sort_order, Category.name, Category.id)
        )
        return [ReportFilterCategoryRow(*row) for row in result.tuples().all()]

    async def list_filter_properties(self, workspace_id: UUID) -> list[ReportFilterPropertyRow]:
        result = await self.session.execute(
            select(Property.id, Property.name, Property.status)
            .where(Property.workspace_id == workspace_id)
            .order_by(Property.status, Property.name, Property.id)
        )
        return [
            ReportFilterPropertyRow(
                id=property_id,
                name=name,
                is_active=property_status == PropertyStatus.ACTIVE,
            )
            for property_id, name, property_status in result.tuples().all()
        ]

    async def read_money_summary(
        self,
        *,
        workspace_id: UUID,
        filters: "ReportingFilters",
    ) -> ReportMoneySummaryRow:
        income = func.coalesce(
            func.sum(case((MoneyEntry.amount > ZERO, MoneyEntry.amount), else_=ZERO)),
            ZERO,
        )
        expense = func.coalesce(
            func.sum(case((MoneyEntry.amount < ZERO, -MoneyEntry.amount), else_=ZERO)),
            ZERO,
        )
        query = select(income, expense).select_from(MoneyEntry).join(Operation)
        query = self._apply_profit_filters(query, workspace_id=workspace_id, filters=filters)
        result = await self.session.execute(query)
        income_value, expense_value = result.one()
        return ReportMoneySummaryRow(
            currency=filters.currency or "",
            income=_money(income_value),
            expense=_money(expense_value),
            profit=_money(income_value - expense_value),
        )

    async def list_account_balances(
        self,
        *,
        workspace_id: UUID,
        filters: "ReportingFilters",
    ) -> list[ReportAccountBalanceRow]:
        confirmed_conditions = [
            Operation.status == OperationStatus.CONFIRMED,
            Operation.workspace_id == workspace_id,
        ]
        if filters.date_to is not None:
            confirmed_conditions.append(Operation.operation_date <= filters.date_to)
        confirmed_total = func.coalesce(
            func.sum(MoneyEntry.amount).filter(*confirmed_conditions),
            ZERO,
        )
        query = (
            select(Account, confirmed_total)
            .outerjoin(
                MoneyEntry,
                and_(
                    MoneyEntry.account_id == Account.id,
                    MoneyEntry.workspace_id == workspace_id,
                    MoneyEntry.currency == Account.currency,
                ),
            )
            .outerjoin(Operation, Operation.id == MoneyEntry.operation_id)
            .where(Account.workspace_id == workspace_id)
            .group_by(Account.id)
            .order_by(Account.is_active.desc(), Account.name, Account.id)
        )
        if filters.account_id is not None:
            query = query.where(Account.id == filters.account_id)
        result = await self.session.execute(query)
        return [
            ReportAccountBalanceRow(
                account_id=account.id,
                name=account.name,
                currency=account.currency,
                balance=_money(account.initial_balance + confirmed_entry_total),
                is_active=account.is_active,
            )
            for account, confirmed_entry_total in result.all()
        ]

    async def list_category_aggregates(
        self,
        *,
        workspace_id: UUID,
        filters: "ReportingFilters",
    ) -> list[ReportCategoryAggregateRow]:
        category_id = case(
            (or_(Category.id.is_(None), Category.system_key == "uncategorized"), None),
            else_=Category.id,
        )
        category_name = case(
            (or_(Category.id.is_(None), Category.system_key == "uncategorized"), "Без категории"),
            else_=Category.name,
        )
        category_active = case(
            (or_(Category.id.is_(None), Category.system_key == "uncategorized"), True),
            else_=Category.is_active,
        )
        income, expense = _aggregate_expressions()
        query = (
            select(category_id, category_name, category_active, income, expense)
            .select_from(MoneyEntry)
            .join(Operation)
            .outerjoin(
                Category,
                and_(
                    Category.id == Operation.category_id,
                    Category.workspace_id == workspace_id,
                ),
            )
        )
        query = self._apply_profit_filters(query, workspace_id=workspace_id, filters=filters)
        query = query.group_by(category_id, category_name, category_active).order_by(
            category_name, category_id
        )
        result = await self.session.execute(query)
        return [
            ReportCategoryAggregateRow(
                category_id=row_category_id,
                name=name,
                currency=filters.currency or "",
                income=_money(row_income),
                expense=_money(row_expense),
                profit=_money(row_income - row_expense),
                is_active=is_active,
            )
            for row_category_id, name, is_active, row_income, row_expense in result.all()
        ]

    async def list_property_aggregates(
        self,
        *,
        workspace_id: UUID,
        filters: "ReportingFilters",
    ) -> list[ReportPropertyAggregateRow]:
        income, expense = _aggregate_expressions()
        query = (
            select(Property.id, Property.name, Property.status, income, expense)
            .select_from(MoneyEntry)
            .join(Operation)
            .join(
                Property,
                and_(
                    Property.id == Operation.property_id,
                    Property.workspace_id == workspace_id,
                ),
            )
        )
        query = self._apply_profit_filters(query, workspace_id=workspace_id, filters=filters)
        query = query.group_by(Property.id).order_by(Property.name, Property.id)
        result = await self.session.execute(query)
        return [
            ReportPropertyAggregateRow(
                property_id=property_id,
                name=name,
                currency=filters.currency or "",
                income=_money(row_income),
                expense=_money(row_expense),
                profit=_money(row_income - row_expense),
                is_active=property_status == PropertyStatus.ACTIVE,
            )
            for property_id, name, property_status, row_income, row_expense in result.all()
        ]

    async def find_next_review_document_id(self, workspace_id: UUID) -> UUID | None:
        result = await self.session.execute(
            select(UploadedDocument.id)
            .where(
                UploadedDocument.workspace_id == workspace_id,
                UploadedDocument.status.in_(
                    {
                        UploadedDocumentStatus.REQUIRES_REVIEW,
                        UploadedDocumentStatus.FAILED_TO_PARSE,
                        UploadedDocumentStatus.PENDING_PARSE,
                    }
                ),
            )
            .order_by(UploadedDocument.created_at, UploadedDocument.id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _apply_profit_filters(
        query: Select,
        *,
        workspace_id: UUID,
        filters: "ReportingFilters",
    ) -> Select:
        query = query.where(
            MoneyEntry.workspace_id == workspace_id,
            MoneyEntry.currency == filters.currency,
            Operation.workspace_id == workspace_id,
            Operation.status == OperationStatus.CONFIRMED,
            Operation.affects_profit.is_(True),
        )
        if filters.date_from is not None:
            query = query.where(Operation.operation_date >= filters.date_from)
        if filters.date_to is not None:
            query = query.where(Operation.operation_date <= filters.date_to)
        if filters.account_id is not None:
            query = query.where(MoneyEntry.account_id == filters.account_id)
        if filters.category_id is not None:
            query = query.where(Operation.category_id == filters.category_id)
        if filters.property_id is not None:
            query = query.where(Operation.property_id == filters.property_id)
        return query


def _aggregate_expressions():
    income = func.coalesce(
        func.sum(case((MoneyEntry.amount > ZERO, MoneyEntry.amount), else_=ZERO)), ZERO
    )
    expense = func.coalesce(
        func.sum(case((MoneyEntry.amount < ZERO, -MoneyEntry.amount), else_=ZERO)), ZERO
    )
    return income, expense


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
