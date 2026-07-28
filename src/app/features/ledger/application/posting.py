"""Create ledger records from already validated financial facts."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account
from app.features.categories.models import Category
from app.features.ledger.domain.money import (
    LedgerPostingPlan,
    ensure_balanced_transfer,
    ensure_distinct_accounts,
    ensure_income_expense_posting,
    ensure_same_currency,
)
from app.features.ledger.mapping.operations import (
    build_bank_pdf_operation,
    build_bank_pdf_transfer_operation,
    build_money_entry,
)
from app.features.ledger.models import Operation
from app.features.ledger.repository import LedgerRepository
from app.features.properties.models import Property
from app.features.workspaces.service import WorkspaceContext


class LedgerPostingService:
    def __init__(self, session: AsyncSession) -> None:
        self.ledger = LedgerRepository(session)

    async def post_imported_income_expense(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
        account: Account,
        plan: LedgerPostingPlan,
        category: Category,
        property_: Property | None,
        idempotency_key: UUID | None,
        idempotency_fingerprint: str | None,
    ) -> Operation:
        ensure_income_expense_posting(plan, account)
        operation = await self.ledger.create_operation(
            build_bank_pdf_operation(
                context=context,
                document_id=document_id,
                raw_transaction_id=raw_transaction_id,
                plan=plan,
                category=category,
                property_=property_,
                idempotency_key=idempotency_key,
                idempotency_fingerprint=idempotency_fingerprint,
            )
        )
        await self.ledger.create_money_entry(
            build_money_entry(
                context=context,
                operation=operation,
                account=account,
                amount=plan.amount,
                entry_order=1,
                balance_after=plan.balance_after,
                extra_metadata={"source": "bank_pdf"},
            )
        )
        return operation

    async def post_imported_transfer(
        self,
        *,
        context: WorkspaceContext,
        source_account: Account,
        source_amount: Decimal,
        source_balance_after: Decimal | None,
        counterparty_account: Account,
        counterparty_amount: Decimal,
        counterparty_balance_after: Decimal | None,
        operation_date: date,
        posting_date: date | None,
        description: str | None,
        transfer_category: Category,
        extra_metadata: dict[str, object],
        idempotency_key: UUID | None,
        idempotency_fingerprint: str | None,
    ) -> Operation:
        ensure_distinct_accounts(source_account.id, counterparty_account.id)
        ensure_same_currency(source_account, counterparty_account)
        ensure_balanced_transfer(source_amount, counterparty_amount)
        operation = await self.ledger.create_operation(
            build_bank_pdf_transfer_operation(
                context=context,
                description=description,
                operation_date=operation_date,
                posting_date=posting_date,
                transfer_category=transfer_category,
                extra_metadata=extra_metadata,
                idempotency_key=idempotency_key,
                idempotency_fingerprint=idempotency_fingerprint,
            )
        )
        await self.ledger.create_money_entry(
            build_money_entry(
                context=context,
                operation=operation,
                account=source_account,
                amount=source_amount,
                entry_order=1,
                balance_after=source_balance_after,
            )
        )
        await self.ledger.create_money_entry(
            build_money_entry(
                context=context,
                operation=operation,
                account=counterparty_account,
                amount=counterparty_amount,
                entry_order=2,
                balance_after=counterparty_balance_after,
            )
        )
        return operation
