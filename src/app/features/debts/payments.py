from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.db.base import utc_now
from app.features.accounts.models import Account, AccountType
from app.features.accounts.repository import AccountRepository
from app.features.categories.models import Category, CategoryKind
from app.features.debts.domain import DebtKind, DebtPaymentPlanner
from app.features.debts.errors import (
    DebtAccountUnavailableError,
    DebtCurrencyMismatchError,
    DebtError,
    DebtIdempotencyConflictError,
    DebtNotFoundError,
    DebtPaymentConflictError,
    DebtPaymentNotFoundError,
)
from app.features.debts.idempotency import DebtCommandFingerprint
from app.features.debts.models import Debt, DebtPayment
from app.features.debts.repository import DebtRepository
from app.features.debts.schemas import RecordDebtPaymentCommand, UndoDebtPaymentCommand
from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.ledger.application.posting import LedgerPostingService
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.models import Operation
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class DebtPaymentMutationOutcome:
    payment: DebtPayment
    replayed: bool


class DebtPaymentRecorder:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.accounts = AccountRepository(session)
        self.debts = DebtRepository(session)
        self.ledger = LedgerRepository(session)
        self.references = LedgerReferenceResolver(session)
        self.posting = LedgerPostingService(session)

    async def record(
        self,
        *,
        context: WorkspaceContext,
        command: RecordDebtPaymentCommand,
    ) -> DebtPaymentMutationOutcome:
        fingerprint = DebtCommandFingerprint.calculate("record_payment", command)
        replay = await self._find_replay(
            context.workspace.id,
            command.idempotency_key,
            fingerprint,
        )
        if replay is not None:
            return DebtPaymentMutationOutcome(payment=replay, replayed=True)

        debt = await self.debts.get_for_workspace_for_update(
            context.workspace.id,
            command.debt_account_id,
        )
        if debt is None:
            raise DebtNotFoundError("Debt was not found in this workspace.")
        replay = await self._find_replay(
            context.workspace.id,
            command.idempotency_key,
            fingerprint,
        )
        if replay is not None:
            return DebtPaymentMutationOutcome(payment=replay, replayed=True)

        debt_account = await self._get_active_debt_account(context.workspace.id, debt)
        settlement_account = await self._get_settlement_account(
            context.workspace.id,
            command.settlement_account_id,
            debt_account.currency,
        )
        balance = debt_account.initial_balance + (
            await self.ledger.get_confirmed_account_entries_total(
                workspace_id=context.workspace.id,
                account_id=debt.account_id,
            )
        )
        plan = DebtPaymentPlanner.build(
            kind=debt.kind,
            balance=balance,
            principal_amount=command.principal_amount,
            interest_amount=command.interest_amount,
        )
        interest_category = await self._get_interest_category(
            workspace_id=context.workspace.id,
            category_id=command.interest_category_id,
            operation_type=plan.interest_operation_type,
        )

        try:
            async with self.session.begin_nested():
                principal = await self._post_principal(
                    context=context,
                    debt=debt,
                    debt_account=debt_account,
                    settlement_account=settlement_account,
                    amount=abs(plan.debt_principal_amount),
                    operation_date=command.operation_date,
                    description=command.description,
                )
                interest = await self._post_interest(
                    context=context,
                    settlement_account=settlement_account,
                    amount=plan.settlement_interest_amount,
                    operation_type=plan.interest_operation_type,
                    operation_date=command.operation_date,
                    description=command.description,
                    category=interest_category,
                )
                payment = await self.debts.create_payment(
                    DebtPayment(
                        workspace_id=context.workspace.id,
                        debt_account_id=debt.account_id,
                        principal_operation_id=principal.id if principal else None,
                        interest_operation_id=interest.id if interest else None,
                        idempotency_key=command.idempotency_key,
                        idempotency_fingerprint=fingerprint,
                        notes=_clean_optional_text(command.notes),
                    )
                )
                return DebtPaymentMutationOutcome(payment=payment, replayed=False)
        except IntegrityError as error:
            replay = await self._find_replay(
                context.workspace.id,
                command.idempotency_key,
                fingerprint,
            )
            if replay is None:
                raise error
            return DebtPaymentMutationOutcome(payment=replay, replayed=True)

    async def _post_principal(
        self,
        *,
        context: WorkspaceContext,
        debt: Debt,
        debt_account: Account,
        settlement_account: Account,
        amount: Decimal,
        operation_date: date,
        description: str | None,
    ) -> Operation | None:
        if amount == Decimal("0.00"):
            return None
        transfer_category = await self.references.get_transfer_category(context.workspace.id)
        source, destination = (
            (debt_account, settlement_account)
            if debt.kind is DebtKind.LOAN_RECEIVABLE
            else (settlement_account, debt_account)
        )
        return await self.posting.post_debt_transfer(
            context=context,
            source_account=source,
            destination_account=destination,
            amount=amount,
            operation_date=operation_date,
            description=description,
            transfer_category=transfer_category,
        )

    async def _post_interest(
        self,
        *,
        context: WorkspaceContext,
        settlement_account: Account,
        amount: Decimal,
        operation_type: OperationType | None,
        operation_date: date,
        description: str | None,
        category: Category | None,
    ) -> Operation | None:
        if operation_type is None:
            return None
        if category is None:
            raise DebtError("Interest category is required when interest is greater than zero.")
        return await self.posting.post_debt_interest(
            context=context,
            account=settlement_account,
            amount=amount,
            operation_type=operation_type,
            operation_date=operation_date,
            description=description,
            category=category,
        )

    async def _find_replay(
        self,
        workspace_id: UUID,
        idempotency_key: UUID,
        fingerprint: str,
    ) -> DebtPayment | None:
        payment = await self.debts.get_payment_by_idempotency_key(
            workspace_id,
            idempotency_key,
        )
        if payment is not None and payment.idempotency_fingerprint != fingerprint:
            raise DebtIdempotencyConflictError(
                "Idempotency key was reused with a different debt payment payload."
            )
        return payment

    async def _get_active_debt_account(self, workspace_id: UUID, debt: Debt) -> Account:
        account = await self.accounts.get_for_workspace(workspace_id, debt.account_id)
        if account is None or account.type is not AccountType.DEBT or not account.is_active:
            raise DebtAccountUnavailableError("Debt account is not active.")
        return account

    async def _get_settlement_account(
        self,
        workspace_id: UUID,
        account_id: UUID,
        currency: str,
    ) -> Account:
        account = await self.accounts.get_for_workspace(workspace_id, account_id)
        if account is None or not account.is_active or account.type is AccountType.DEBT:
            raise DebtAccountUnavailableError(
                "Settlement account is not active or does not belong to this workspace."
            )
        if account.currency != currency:
            raise DebtCurrencyMismatchError("Debt and settlement account currencies must match.")
        return account

    async def _get_interest_category(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID | None,
        operation_type: OperationType | None,
    ) -> Category | None:
        if operation_type is None:
            return None
        if category_id is None:
            raise DebtError("Interest category is required when interest is greater than zero.")
        category = await self.references.get_category_or_uncategorized(
            workspace_id,
            category_id,
        )
        expected_kind = (
            CategoryKind.INCOME if operation_type is OperationType.INCOME else CategoryKind.EXPENSE
        )
        if category.kind not in {expected_kind, CategoryKind.MIXED}:
            raise DebtError("Interest category does not match the payment direction.")
        return category


class DebtPaymentReverser:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.debts = DebtRepository(session)
        self.ledger = LedgerRepository(session)

    async def reverse(
        self,
        *,
        context: WorkspaceContext,
        command: UndoDebtPaymentCommand,
    ) -> DebtPaymentMutationOutcome:
        payment = await self.debts.get_payment_for_workspace_for_update(
            context.workspace.id,
            command.payment_id,
        )
        if payment is None:
            raise DebtPaymentNotFoundError("Debt payment was not found.")
        operations = await self._get_operations(context.workspace.id, payment)
        self._ensure_debt_operations(operations)
        if payment.reversed_at is not None:
            self._ensure_replayed_state(operations)
            return DebtPaymentMutationOutcome(payment=payment, replayed=True)

        self._ensure_expected_versions(command, payment, operations)
        for operation in operations:
            if operation.status is not OperationStatus.CONFIRMED:
                raise DebtPaymentConflictError("Only a confirmed debt payment can be undone.")
            operation.status = OperationStatus.IGNORED
            operation.updated_by_user_id = context.user.id
        payment.reversed_at = utc_now()
        try:
            await self.session.flush()
        except StaleDataError as error:
            raise DebtPaymentConflictError(
                "Debt payment was changed by another request."
            ) from error
        return DebtPaymentMutationOutcome(payment=payment, replayed=False)

    async def _get_operations(
        self,
        workspace_id: UUID,
        payment: DebtPayment,
    ) -> list[Operation]:
        operations: list[Operation] = []
        for operation_id in (
            payment.principal_operation_id,
            payment.interest_operation_id,
        ):
            if operation_id is None:
                continue
            operation = await self.ledger.get_operation_for_workspace_for_update(
                workspace_id=workspace_id,
                operation_id=operation_id,
            )
            if operation is None:
                raise DebtPaymentConflictError("Payment operation was not found.")
            operations.append(operation)
        return operations

    @staticmethod
    def _ensure_expected_versions(
        command: UndoDebtPaymentCommand,
        payment: DebtPayment,
        operations: list[Operation],
    ) -> None:
        if payment.principal_operation_id is None and (
            command.expected_principal_operation_version is not None
        ):
            raise DebtPaymentConflictError("Principal operation version is unexpected.")
        if payment.interest_operation_id is None and (
            command.expected_interest_operation_version is not None
        ):
            raise DebtPaymentConflictError("Interest operation version is unexpected.")
        expected_by_id = {
            payment.principal_operation_id: command.expected_principal_operation_version,
            payment.interest_operation_id: command.expected_interest_operation_version,
        }
        if any(expected_by_id[operation.id] != operation.version for operation in operations):
            raise DebtPaymentConflictError("Debt payment was changed by another request.")

    @staticmethod
    def _ensure_replayed_state(operations: list[Operation]) -> None:
        if any(operation.status is not OperationStatus.IGNORED for operation in operations):
            raise DebtPaymentConflictError("Reversed payment operations are inconsistent.")

    @staticmethod
    def _ensure_debt_operations(operations: list[Operation]) -> None:
        if any(operation.source is not OperationSource.DEBT for operation in operations):
            raise DebtPaymentConflictError("Payment contains a non-debt operation.")


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None
