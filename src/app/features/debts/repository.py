from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.features.accounts.models import Account, AccountType
from app.features.debts.domain import DebtKind
from app.features.debts.models import Debt, DebtPayment
from app.features.imports.models import RawTransaction, UploadedDocument
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.models import MoneyEntry, Operation


@dataclass(frozen=True)
class DebtReadRow:
    account_id: UUID
    name: str
    kind: DebtKind
    currency: str
    initial_balance: Decimal
    confirmed_entry_total: Decimal
    is_active: bool
    opened_on: date | None
    original_principal: Decimal | None
    maturity_date: date | None
    credit_limit: Decimal | None
    notes: str | None
    updated_at: datetime
    has_payment_account: bool
    has_delete_blockers: bool


@dataclass(frozen=True)
class DebtOperationReadRow:
    operation_id: UUID
    version: int
    operation_date: date
    operation_type: OperationType
    status: OperationStatus
    description: str | None
    amount: Decimal


@dataclass(frozen=True)
class DebtPaymentHistoryRow:
    payment_id: UUID
    principal: DebtOperationReadRow | None
    interest: DebtOperationReadRow | None
    notes: str | None
    created_at: datetime
    reversed_at: datetime | None


@dataclass(frozen=True)
class DebtPaymentHistoryStats:
    total: int
    principal: Decimal
    interest: Decimal


class DebtRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_workspace(self, workspace_id: UUID, account_id: UUID) -> Debt | None:
        result = await self.session.execute(
            select(Debt).where(
                Debt.account_id == account_id,
                Debt.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_for_workspace_for_update(
        self,
        workspace_id: UUID,
        account_id: UUID,
    ) -> Debt | None:
        result = await self.session.execute(
            select(Debt)
            .where(
                Debt.account_id == account_id,
                Debt.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_creation_idempotency_key(
        self,
        workspace_id: UUID,
        idempotency_key: UUID,
    ) -> Debt | None:
        result = await self.session.execute(
            select(Debt).where(
                Debt.workspace_id == workspace_id,
                Debt.creation_idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, debt: Debt) -> Debt:
        self.session.add(debt)
        await self.session.flush()
        return debt

    async def list_active_credit_card_accounts(self, workspace_id: UUID) -> list[Account]:
        result = await self.session.execute(
            select(Account)
            .join(
                Debt,
                and_(
                    Debt.account_id == Account.id,
                    Debt.workspace_id == workspace_id,
                ),
            )
            .where(
                Account.workspace_id == workspace_id,
                Account.is_active.is_(True),
                Account.type == AccountType.DEBT,
                Debt.kind == DebtKind.CREDIT_CARD,
            )
            .order_by(Account.created_at)
        )
        return list(result.scalars().all())

    async def get_payment_for_workspace(
        self,
        workspace_id: UUID,
        payment_id: UUID,
    ) -> DebtPayment | None:
        result = await self.session.execute(
            select(DebtPayment).where(
                DebtPayment.id == payment_id,
                DebtPayment.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_payment_for_workspace_for_update(
        self,
        workspace_id: UUID,
        payment_id: UUID,
    ) -> DebtPayment | None:
        result = await self.session.execute(
            select(DebtPayment)
            .where(
                DebtPayment.id == payment_id,
                DebtPayment.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_payment_by_idempotency_key(
        self,
        workspace_id: UUID,
        idempotency_key: UUID,
    ) -> DebtPayment | None:
        result = await self.session.execute(
            select(DebtPayment).where(
                DebtPayment.workspace_id == workspace_id,
                DebtPayment.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def create_payment(self, payment: DebtPayment) -> DebtPayment:
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def has_payments(self, workspace_id: UUID, debt_account_id: UUID) -> bool:
        result = await self.session.execute(
            select(DebtPayment.id)
            .where(
                DebtPayment.workspace_id == workspace_id,
                DebtPayment.debt_account_id == debt_account_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_account_operations(
        self,
        workspace_id: UUID,
        debt_account_id: UUID,
    ) -> list[Operation]:
        result = await self.session.execute(
            select(Operation)
            .join(
                MoneyEntry,
                and_(
                    MoneyEntry.operation_id == Operation.id,
                    MoneyEntry.workspace_id == workspace_id,
                ),
            )
            .where(
                Operation.workspace_id == workspace_id,
                MoneyEntry.account_id == debt_account_id,
            )
            .distinct()
        )
        return list(result.scalars().all())

    async def list_read_rows(self, workspace_id: UUID) -> list[DebtReadRow]:
        result = await self.session.execute(
            self._read_query(workspace_id).order_by(
                Account.is_active.desc(),
                Debt.created_at.desc(),
            )
        )
        return [self._debt_read_row(*row) for row in result.all()]

    async def get_read_row(
        self,
        workspace_id: UUID,
        account_id: UUID,
    ) -> DebtReadRow | None:
        result = await self.session.execute(
            self._read_query(workspace_id).where(Debt.account_id == account_id)
        )
        row = result.one_or_none()
        return None if row is None else self._debt_read_row(*row)

    async def list_payment_history(
        self,
        *,
        workspace_id: UUID,
        debt_account_id: UUID,
        offset: int,
        limit: int,
    ) -> list[DebtPaymentHistoryRow]:
        principal_operation = aliased(Operation)
        interest_operation = aliased(Operation)
        principal_amount = (
            select(func.coalesce(func.abs(func.sum(MoneyEntry.amount)), Decimal("0.00")))
            .where(
                MoneyEntry.workspace_id == workspace_id,
                MoneyEntry.account_id == DebtPayment.debt_account_id,
                MoneyEntry.operation_id == DebtPayment.principal_operation_id,
            )
            .correlate(DebtPayment)
            .scalar_subquery()
        )
        interest_amount = (
            select(func.coalesce(func.abs(func.sum(MoneyEntry.amount)), Decimal("0.00")))
            .where(
                MoneyEntry.workspace_id == workspace_id,
                MoneyEntry.operation_id == DebtPayment.interest_operation_id,
            )
            .correlate(DebtPayment)
            .scalar_subquery()
        )
        result = await self.session.execute(
            select(
                DebtPayment,
                principal_operation,
                interest_operation,
                principal_amount,
                interest_amount,
            )
            .outerjoin(
                principal_operation,
                and_(
                    principal_operation.id == DebtPayment.principal_operation_id,
                    principal_operation.workspace_id == workspace_id,
                ),
            )
            .outerjoin(
                interest_operation,
                and_(
                    interest_operation.id == DebtPayment.interest_operation_id,
                    interest_operation.workspace_id == workspace_id,
                ),
            )
            .where(
                DebtPayment.workspace_id == workspace_id,
                DebtPayment.debt_account_id == debt_account_id,
            )
            .order_by(DebtPayment.created_at.desc(), DebtPayment.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return [
            DebtPaymentHistoryRow(
                payment_id=payment.id,
                principal=self._operation_read_row(principal, principal_total),
                interest=self._operation_read_row(interest, interest_total),
                notes=payment.notes,
                created_at=payment.created_at,
                reversed_at=payment.reversed_at,
            )
            for (
                payment,
                principal,
                interest,
                principal_total,
                interest_total,
            ) in result.all()
        ]

    async def get_payment_history_stats(
        self,
        *,
        workspace_id: UUID,
        debt_account_id: UUID,
    ) -> DebtPaymentHistoryStats:
        principal_total = (
            select(func.coalesce(func.sum(func.abs(MoneyEntry.amount)), Decimal("0.00")))
            .join(
                DebtPayment,
                DebtPayment.principal_operation_id == MoneyEntry.operation_id,
            )
            .join(
                Operation,
                and_(
                    Operation.id == MoneyEntry.operation_id,
                    Operation.workspace_id == workspace_id,
                    Operation.status == OperationStatus.CONFIRMED,
                ),
            )
            .where(
                DebtPayment.workspace_id == workspace_id,
                DebtPayment.debt_account_id == debt_account_id,
                MoneyEntry.workspace_id == workspace_id,
                MoneyEntry.account_id == debt_account_id,
            )
            .scalar_subquery()
        )
        interest_total = (
            select(func.coalesce(func.sum(func.abs(MoneyEntry.amount)), Decimal("0.00")))
            .join(
                DebtPayment,
                DebtPayment.interest_operation_id == MoneyEntry.operation_id,
            )
            .join(
                Operation,
                and_(
                    Operation.id == MoneyEntry.operation_id,
                    Operation.workspace_id == workspace_id,
                    Operation.status == OperationStatus.CONFIRMED,
                ),
            )
            .where(
                DebtPayment.workspace_id == workspace_id,
                DebtPayment.debt_account_id == debt_account_id,
                MoneyEntry.workspace_id == workspace_id,
            )
            .scalar_subquery()
        )
        result = await self.session.execute(
            select(
                func.count(DebtPayment.id),
                principal_total,
                interest_total,
            ).where(
                DebtPayment.workspace_id == workspace_id,
                DebtPayment.debt_account_id == debt_account_id,
            )
        )
        total, principal, interest = result.one()
        return DebtPaymentHistoryStats(
            total=total,
            principal=principal,
            interest=interest,
        )

    @staticmethod
    def _read_query(workspace_id: UUID) -> Select[Any]:
        payment_account = aliased(Account)
        confirmed_entry_total = func.coalesce(
            func.sum(MoneyEntry.amount).filter(Operation.status == OperationStatus.CONFIRMED),
            Decimal("0.00"),
        )
        has_payment_account = (
            select(payment_account.id)
            .where(
                payment_account.workspace_id == workspace_id,
                payment_account.is_active.is_(True),
                payment_account.type != AccountType.DEBT,
                payment_account.currency == Account.currency,
            )
            .exists()
        )
        opening_transfer_count = (
            select(func.count(func.distinct(Operation.id)))
            .select_from(MoneyEntry)
            .join(
                Operation,
                and_(
                    Operation.id == MoneyEntry.operation_id,
                    Operation.workspace_id == workspace_id,
                ),
            )
            .where(
                MoneyEntry.workspace_id == workspace_id,
                MoneyEntry.account_id == Debt.account_id,
                Operation.source == OperationSource.DEBT,
                Operation.type == OperationType.TRANSFER,
            )
            .correlate(Debt)
            .scalar_subquery()
        )
        has_blocking_entry = (
            select(MoneyEntry.id)
            .join(
                Operation,
                and_(
                    Operation.id == MoneyEntry.operation_id,
                    Operation.workspace_id == workspace_id,
                ),
            )
            .where(
                MoneyEntry.workspace_id == workspace_id,
                MoneyEntry.account_id == Debt.account_id,
                ~and_(
                    Operation.source == OperationSource.DEBT,
                    Operation.type == OperationType.TRANSFER,
                ),
            )
            .correlate(Debt)
            .exists()
        )
        has_delete_blockers = (
            has_blocking_entry
            | (opening_transfer_count > 1)
            | select(UploadedDocument.id)
            .where(
                UploadedDocument.workspace_id == workspace_id,
                UploadedDocument.account_id == Debt.account_id,
            )
            .correlate(Debt)
            .exists()
            | select(RawTransaction.id)
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.account_id == Debt.account_id,
            )
            .correlate(Debt)
            .exists()
            | select(DebtPayment.id)
            .where(
                DebtPayment.workspace_id == workspace_id,
                DebtPayment.debt_account_id == Debt.account_id,
            )
            .correlate(Debt)
            .exists()
        )
        return (
            select(
                Debt,
                Account,
                confirmed_entry_total,
                has_payment_account,
                has_delete_blockers,
            )
            .join(
                Account,
                and_(
                    Account.id == Debt.account_id,
                    Account.workspace_id == workspace_id,
                ),
            )
            .outerjoin(
                MoneyEntry,
                and_(
                    MoneyEntry.account_id == Debt.account_id,
                    MoneyEntry.workspace_id == workspace_id,
                ),
            )
            .outerjoin(
                Operation,
                and_(
                    Operation.id == MoneyEntry.operation_id,
                    Operation.workspace_id == workspace_id,
                ),
            )
            .where(Debt.workspace_id == workspace_id)
            .group_by(Debt.account_id, Account.id)
        )

    @staticmethod
    def _debt_read_row(
        debt: Debt,
        account: Account,
        confirmed_entry_total: Decimal,
        has_payment_account: bool,
        has_delete_blockers: bool,
    ) -> DebtReadRow:
        return DebtReadRow(
            account_id=debt.account_id,
            name=account.name,
            kind=debt.kind,
            currency=account.currency,
            initial_balance=account.initial_balance,
            confirmed_entry_total=confirmed_entry_total,
            is_active=account.is_active,
            opened_on=debt.opened_on,
            original_principal=debt.original_principal,
            maturity_date=debt.maturity_date,
            credit_limit=debt.credit_limit,
            notes=account.notes,
            updated_at=debt.updated_at,
            has_payment_account=has_payment_account,
            has_delete_blockers=has_delete_blockers,
        )

    @staticmethod
    def _operation_read_row(
        operation: Operation | None,
        amount: Decimal,
    ) -> DebtOperationReadRow | None:
        if operation is None:
            return None
        return DebtOperationReadRow(
            operation_id=operation.id,
            version=operation.version,
            operation_date=operation.operation_date,
            operation_type=operation.type,
            status=operation.status,
            description=operation.description,
            amount=amount,
        )
