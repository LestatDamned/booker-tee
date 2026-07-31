from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.import_review.repository import ImportReviewRepository
from app.features.imports.documents.repository import DocumentRepository
from app.features.reports.service import ReportFilters, ReportsService
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class ChatPrivateStatus:
    documents_needing_attention: int
    raw_transactions_needing_attention: int

    @property
    def total_needing_attention(self) -> int:
        return self.documents_needing_attention + self.raw_transactions_needing_attention


@dataclass(frozen=True)
class ChatMonthlySummary:
    date_from: date
    date_to: date
    currency: str
    income: Decimal
    expense: Decimal
    profit: Decimal
    documents_needing_attention: int
    raw_transactions_needing_attention: int

    @property
    def total_needing_attention(self) -> int:
        return self.documents_needing_attention + self.raw_transactions_needing_attention


@dataclass(frozen=True)
class ChatCategorySummaryRow:
    category_name: str
    income: Decimal
    expense: Decimal
    profit: Decimal


@dataclass(frozen=True)
class ChatCategorySummary:
    date_from: date
    date_to: date
    currency: str
    rows: tuple[ChatCategorySummaryRow, ...]


@dataclass(frozen=True)
class ChatAccountBalanceRow:
    account_name: str
    currency: str
    balance: Decimal


@dataclass(frozen=True)
class ChatCurrencyBalanceTotal:
    currency: str
    balance: Decimal


@dataclass(frozen=True)
class ChatAccountBalances:
    rows: tuple[ChatAccountBalanceRow, ...]
    totals: tuple[ChatCurrencyBalanceTotal, ...]


class ChatPrivateStatusReader:
    def __init__(self, session: AsyncSession) -> None:
        self.documents = DocumentRepository(session)
        self.import_review = ImportReviewRepository(session)

    async def read_status(self, context: WorkspaceContext) -> ChatPrivateStatus:
        raw_transactions_count = await self.import_review.count_raw_transactions_needing_attention(
            context.workspace.id
        )
        return ChatPrivateStatus(
            documents_needing_attention=await self.documents.count_documents_needing_attention(
                context.workspace.id
            ),
            raw_transactions_needing_attention=raw_transactions_count,
        )


class ChatMonthlySummaryReader:
    def __init__(self, session: AsyncSession) -> None:
        self.documents = DocumentRepository(session)
        self.import_review = ImportReviewRepository(session)
        self.reports = ReportsService(session)

    async def read_current_month_summary(self, context: WorkspaceContext) -> ChatMonthlySummary:
        today = utc_now().date()
        return await self.read_month_summary(
            context=context,
            month_start=today.replace(day=1),
        )

    async def read_month_summary(
        self,
        *,
        context: WorkspaceContext,
        month_start: date,
    ) -> ChatMonthlySummary:
        date_from = month_start.replace(day=1)
        date_to = ChatMonthRange.next_month_start(date_from) - timedelta(days=1)
        overview = await self.reports.build_overview(
            workspace_id=context.workspace.id,
            filters=ReportFilters(
                date_from=date_from,
                date_to=date_to,
                currency=getattr(context.workspace, "default_currency", "RUB"),
            ),
        )
        return ChatMonthlySummary(
            date_from=date_from,
            date_to=date_to,
            currency=getattr(context.workspace, "default_currency", "RUB"),
            income=overview.summary.income,
            expense=overview.summary.expense,
            profit=overview.summary.profit,
            documents_needing_attention=await self.documents.count_documents_needing_attention(
                context.workspace.id
            ),
            raw_transactions_needing_attention=(
                await self.import_review.count_raw_transactions_needing_attention(
                    context.workspace.id
                )
            ),
        )

    async def read_category_summary(
        self,
        *,
        context: WorkspaceContext,
        month_start: date,
    ) -> ChatCategorySummary:
        date_from = month_start.replace(day=1)
        date_to = ChatMonthRange.next_month_start(date_from) - timedelta(days=1)
        overview = await self.reports.build_overview(
            workspace_id=context.workspace.id,
            filters=ReportFilters(
                date_from=date_from,
                date_to=date_to,
                currency=getattr(context.workspace, "default_currency", "RUB"),
            ),
        )
        return ChatCategorySummary(
            date_from=date_from,
            date_to=date_to,
            currency=getattr(context.workspace, "default_currency", "RUB"),
            rows=tuple(
                ChatCategorySummaryRow(
                    category_name=row.category_name,
                    income=row.income,
                    expense=row.expense,
                    profit=row.profit,
                )
                for row in overview.categories
            ),
        )


class ChatAccountBalanceReader:
    def __init__(self, session: AsyncSession) -> None:
        self.reports = ReportsService(session)

    async def read_account_balances(self, context: WorkspaceContext) -> ChatAccountBalances:
        overview = await self.reports.build_overview(
            workspace_id=context.workspace.id,
            filters=ReportFilters(),
        )
        rows = tuple(
            ChatAccountBalanceRow(
                account_name=balance_row.account.name,
                currency=balance_row.account.currency,
                balance=balance_row.balance,
            )
            for balance_row in overview.account_balances
        )
        return ChatAccountBalances(
            rows=rows,
            totals=ChatAccountBalanceTotalBuilder.build_totals(rows),
        )


class ChatAccountBalanceTotalBuilder:
    @staticmethod
    def build_totals(
        rows: tuple[ChatAccountBalanceRow, ...],
    ) -> tuple[ChatCurrencyBalanceTotal, ...]:
        grouped: dict[str, Decimal] = {}
        for row in rows:
            grouped[row.currency] = grouped.get(row.currency, Decimal("0.00")) + row.balance
        return tuple(
            ChatCurrencyBalanceTotal(currency=currency, balance=balance.quantize(Decimal("0.01")))
            for currency, balance in sorted(grouped.items())
        )


class ChatMonthRange:
    @staticmethod
    def next_month_start(month_start: date) -> date:
        if month_start.month == 12:
            return month_start.replace(year=month_start.year + 1, month=1)
        return month_start.replace(month=month_start.month + 1)
