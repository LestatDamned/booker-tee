from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account
from app.features.accounts.repository import AccountRepository
from app.features.ledger.models import Operation, OperationType
from app.features.ledger.repository import LedgerRepository

MONEY_ZERO = Decimal("0.00")


@dataclass(frozen=True)
class ReportFilters:
    date_from: date | None = None
    date_to: date | None = None
    account_id: UUID | None = None
    category_id: UUID | None = None
    property_id: UUID | None = None


@dataclass(frozen=True)
class AccountBalanceRow:
    account: Account
    balance: Decimal


@dataclass(frozen=True)
class IncomeExpenseSummary:
    income: Decimal
    expense: Decimal
    profit: Decimal


@dataclass(frozen=True)
class CategorySummaryRow:
    category_name: str
    income: Decimal
    expense: Decimal
    profit: Decimal


@dataclass(frozen=True)
class PropertySummaryRow:
    property_name: str
    income: Decimal
    expense: Decimal
    profit: Decimal


@dataclass(frozen=True)
class UncategorizedOperationRow:
    operation: Operation
    total: Decimal


@dataclass(frozen=True)
class ReportsOverview:
    account_balances: list[AccountBalanceRow]
    summary: IncomeExpenseSummary
    categories: list[CategorySummaryRow]
    properties: list[PropertySummaryRow]
    uncategorized: list[UncategorizedOperationRow]


class ReportsService:
    def __init__(self, session: AsyncSession) -> None:
        self.accounts = AccountRepository(session)
        self.ledger = LedgerRepository(session)

    async def build_overview(
        self,
        *,
        workspace_id: UUID,
        filters: ReportFilters,
    ) -> ReportsOverview:
        accounts = await self.accounts.list_active_for_workspace(workspace_id)
        account_balances = [
            AccountBalanceRow(
                account=account,
                balance=(
                    account.initial_balance
                    + await self.ledger.get_confirmed_account_entries_total(
                        workspace_id=workspace_id,
                        account_id=account.id,
                    )
                ).quantize(Decimal("0.01")),
            )
            for account in accounts
        ]
        operations = await self.ledger.list_confirmed_operations_for_report(
            workspace_id=workspace_id,
            date_from=filters.date_from,
            date_to=filters.date_to,
            account_id=filters.account_id,
            category_id=filters.category_id,
            property_id=filters.property_id,
        )
        profit_operations = [operation for operation in operations if operation.affects_profit]
        return ReportsOverview(
            account_balances=account_balances,
            summary=summarize_income_expense(profit_operations),
            categories=summarize_by_category(profit_operations),
            properties=summarize_by_property(profit_operations),
            uncategorized=list_uncategorized_operations(profit_operations),
        )


def summarize_income_expense(operations: list[Operation]) -> IncomeExpenseSummary:
    income = MONEY_ZERO
    expense = MONEY_ZERO
    for operation in operations:
        total = operation_signed_total(operation)
        if operation.type == OperationType.INCOME or total > MONEY_ZERO:
            income += max(total, MONEY_ZERO)
        elif operation.type == OperationType.EXPENSE or total < MONEY_ZERO:
            expense += abs(min(total, MONEY_ZERO))
    return IncomeExpenseSummary(
        income=income.quantize(Decimal("0.01")),
        expense=expense.quantize(Decimal("0.01")),
        profit=(income - expense).quantize(Decimal("0.01")),
    )


def summarize_by_category(operations: list[Operation]) -> list[CategorySummaryRow]:
    grouped: dict[str, list[Operation]] = {}
    for operation in operations:
        category_name = operation.category.name if operation.category else "Без категории"
        grouped.setdefault(category_name, []).append(operation)
    return [
        CategorySummaryRow(
            category_name=category_name,
            income=summary.income,
            expense=summary.expense,
            profit=summary.profit,
        )
        for category_name, summary in sorted(
            (
                (category_name, summarize_income_expense(category_operations))
                for category_name, category_operations in grouped.items()
            ),
            key=lambda item: item[0],
        )
    ]


def summarize_by_property(operations: list[Operation]) -> list[PropertySummaryRow]:
    grouped: dict[str, list[Operation]] = {}
    for operation in operations:
        if operation.property is None:
            continue
        grouped.setdefault(operation.property.name, []).append(operation)
    return [
        PropertySummaryRow(
            property_name=property_name,
            income=summary.income,
            expense=summary.expense,
            profit=summary.profit,
        )
        for property_name, summary in sorted(
            (
                (property_name, summarize_income_expense(property_operations))
                for property_name, property_operations in grouped.items()
            ),
            key=lambda item: item[0],
        )
    ]


def list_uncategorized_operations(operations: list[Operation]) -> list[UncategorizedOperationRow]:
    rows: list[UncategorizedOperationRow] = []
    for operation in operations:
        if operation.category is not None and operation.category.system_key != "uncategorized":
            continue
        rows.append(
            UncategorizedOperationRow(
                operation=operation,
                total=operation_signed_total(operation),
            )
        )
    return rows


def operation_signed_total(operation: Operation) -> Decimal:
    return sum((entry.amount for entry in operation.money_entries), MONEY_ZERO).quantize(
        Decimal("0.01")
    )
