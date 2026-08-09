from collections.abc import Sequence
from decimal import Decimal
from math import ceil
from typing import Protocol
from uuid import UUID

from app.features.debts.domain import DebtBalance, DebtKind, DebtPolicy, DebtPortfolio
from app.features.debts.repository import (
    DebtPaymentHistoryRow,
    DebtPaymentHistoryStats,
    DebtReadRow,
)
from app.features.debts.schemas import (
    DebtCapabilitiesDto,
    DebtCurrencyTotalsDto,
    DebtDetailDto,
    DebtPaymentHistoryItemDto,
    DebtPaymentHistoryPageDto,
    DebtPaymentOperationDto,
    DebtPaymentTotalsDto,
    DebtPortfolioDto,
    DebtSummaryDto,
)

DEFAULT_PAYMENT_PAGE_SIZE = 20
MAX_PAYMENT_PAGE_SIZE = 100


class DebtReadSource(Protocol):
    async def list_read_rows(self, workspace_id: UUID) -> Sequence[DebtReadRow]: ...

    async def get_read_row(
        self,
        workspace_id: UUID,
        account_id: UUID,
    ) -> DebtReadRow | None: ...

    async def list_payment_history(
        self,
        *,
        workspace_id: UUID,
        debt_account_id: UUID,
        offset: int,
        limit: int,
    ) -> Sequence[DebtPaymentHistoryRow]: ...

    async def get_payment_history_stats(
        self,
        *,
        workspace_id: UUID,
        debt_account_id: UUID,
    ) -> DebtPaymentHistoryStats: ...


class DebtReader:
    def __init__(self, debts: DebtReadSource) -> None:
        self._debts = debts

    async def list(
        self,
        *,
        workspace_id: UUID,
        can_write: bool,
    ) -> DebtPortfolioDto:
        rows = await self._debts.list_read_rows(workspace_id)
        items = [self._summary(row, can_write=can_write) for row in rows]
        totals = DebtPortfolio.summarize(
            DebtBalance(kind=item.kind, currency=item.currency, balance=item.balance)
            for item in items
        )
        return DebtPortfolioDto(
            items=items,
            totals=[DebtCurrencyTotalsDto.model_validate(total) for total in totals],
        )

    async def get_detail(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        can_write: bool,
        payments_page: int = 1,
        payments_page_size: int = DEFAULT_PAYMENT_PAGE_SIZE,
    ) -> DebtDetailDto | None:
        row = await self._debts.get_read_row(workspace_id, account_id)
        if row is None:
            return None
        page = max(1, payments_page)
        page_size = min(MAX_PAYMENT_PAGE_SIZE, max(1, payments_page_size))
        stats = await self._debts.get_payment_history_stats(
            workspace_id=workspace_id,
            debt_account_id=account_id,
        )
        history = await self._debts.list_payment_history(
            workspace_id=workspace_id,
            debt_account_id=account_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        total_pages = max(1, ceil(stats.total / page_size))
        return DebtDetailDto(
            debt=self._summary(row, can_write=can_write),
            notes=row.notes,
            payment_totals=DebtPaymentTotalsDto(
                principal=stats.principal,
                interest=stats.interest,
            ),
            payments=DebtPaymentHistoryPageDto(
                items=[self._payment(item, can_write=can_write) for item in history],
                page=page,
                page_size=page_size,
                total=stats.total,
                total_pages=total_pages,
                has_previous=page > 1,
                has_next=page < total_pages,
            ),
        )

    @staticmethod
    def _summary(row: DebtReadRow, *, can_write: bool) -> DebtSummaryDto:
        balance = (row.initial_balance + row.confirmed_entry_total).quantize(Decimal("0.01"))
        capabilities = DebtPolicy.resolve_capabilities(
            kind=row.kind,
            balance=balance,
            can_write=can_write,
            is_active=row.is_active,
            has_payment_account=row.has_payment_account,
            has_delete_blockers=row.has_delete_blockers,
        )
        return DebtSummaryDto(
            account_id=row.account_id,
            name=row.name,
            kind=row.kind,
            currency=row.currency,
            balance=balance,
            outstanding=DebtPolicy.outstanding(row.kind, balance),
            status=DebtPolicy.resolve_status(
                kind=row.kind,
                balance=balance,
                is_active=row.is_active,
            ),
            opened_on=row.opened_on,
            original_principal=row.original_principal,
            maturity_date=row.maturity_date,
            credit_limit=row.credit_limit,
            available_credit=(
                DebtPolicy.calculate_available_credit(
                    credit_limit=row.credit_limit,
                    balance=balance,
                )
                if row.kind is DebtKind.CREDIT_CARD and row.credit_limit is not None
                else None
            ),
            is_active=row.is_active,
            updated_at=row.updated_at,
            capabilities=DebtCapabilitiesDto.model_validate(capabilities),
        )

    @staticmethod
    def _payment(
        row: DebtPaymentHistoryRow,
        *,
        can_write: bool,
    ) -> DebtPaymentHistoryItemDto:
        return DebtPaymentHistoryItemDto(
            payment_id=row.payment_id,
            principal=(
                DebtPaymentOperationDto.model_validate(row.principal)
                if row.principal is not None
                else None
            ),
            interest=(
                DebtPaymentOperationDto.model_validate(row.interest)
                if row.interest is not None
                else None
            ),
            notes=row.notes,
            created_at=row.created_at,
            reversed_at=row.reversed_at,
            can_undo=can_write and row.reversed_at is None,
        )
