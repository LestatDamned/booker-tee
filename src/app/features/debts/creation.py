from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account, AccountType
from app.features.accounts.repository import AccountRepository
from app.features.accounts.service import clean_required_text, normalize_currency
from app.features.debts.domain import DebtKind, DebtPolicy
from app.features.debts.errors import (
    DebtAccountUnavailableError,
    DebtCurrencyMismatchError,
    DebtError,
    DebtIdempotencyConflictError,
)
from app.features.debts.idempotency import DebtCommandFingerprint
from app.features.debts.models import Debt
from app.features.debts.repository import DebtRepository
from app.features.debts.schemas import (
    AddExistingDebtCommand,
    GiveLoanCommand,
    OpenCreditCardCommand,
    TakeLoanCommand,
)
from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.ledger.application.posting import LedgerPostingService
from app.features.ledger.domain.money import normalize_positive_money
from app.features.workspaces.service import WorkspaceContext

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class DebtOpeningTransfer:
    account: Account
    amount: Decimal
    operation_date: date
    description: str | None


@dataclass(frozen=True)
class DebtCreationPlan:
    name: str
    currency: str
    kind: DebtKind
    initial_balance: Decimal
    original_principal: Decimal | None
    opened_on: date | None
    maturity_date: date | None
    credit_limit: Decimal | None
    notes: str | None
    idempotency_key: UUID
    fingerprint: str
    opening_transfer: DebtOpeningTransfer | None = None


class DebtCreator:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.accounts = AccountRepository(session)
        self.debts = DebtRepository(session)
        self.references = LedgerReferenceResolver(session)
        self.posting = LedgerPostingService(session)

    async def add_existing_debt(
        self,
        *,
        context: WorkspaceContext,
        command: AddExistingDebtCommand,
    ) -> Debt:
        fingerprint = DebtCommandFingerprint.calculate("add_existing_debt", command)
        replay = await self._find_replay(context.workspace.id, command.idempotency_key, fingerprint)
        if replay is not None:
            return replay
        if command.kind is DebtKind.CREDIT_CARD:
            raise DebtError("Use open_credit_card for credit card debt.")
        signed_balance = (
            command.opening_balance
            if command.kind is DebtKind.LOAN_RECEIVABLE
            else -command.opening_balance
        )
        DebtPolicy.validate_terms(
            kind=command.kind,
            opening_balance=signed_balance,
            opened_on=command.opened_on,
            maturity_date=command.maturity_date,
            original_principal=command.original_principal,
            credit_limit=None,
        )
        amount = normalize_positive_money(command.opening_balance)
        signed_balance = amount if command.kind is DebtKind.LOAN_RECEIVABLE else -amount
        return await self._create(
            context=context,
            plan=DebtCreationPlan(
                name=clean_required_text(command.name, "Debt name is required."),
                currency=normalize_currency(command.currency),
                kind=command.kind,
                initial_balance=signed_balance,
                original_principal=command.original_principal.quantize(Decimal("0.01")),
                opened_on=command.opened_on,
                maturity_date=command.maturity_date,
                credit_limit=None,
                notes=command.notes,
                idempotency_key=command.idempotency_key,
                fingerprint=fingerprint,
            ),
        )

    async def give_loan(
        self,
        *,
        context: WorkspaceContext,
        command: GiveLoanCommand,
    ) -> Debt:
        fingerprint = DebtCommandFingerprint.calculate("give_loan", command)
        replay = await self._find_replay(context.workspace.id, command.idempotency_key, fingerprint)
        if replay is not None:
            return replay
        DebtPolicy.validate_terms(
            kind=DebtKind.LOAN_RECEIVABLE,
            opening_balance=ZERO,
            opened_on=command.opened_on,
            maturity_date=command.maturity_date,
            original_principal=command.amount,
            credit_limit=None,
        )
        amount = normalize_positive_money(command.amount)
        currency = normalize_currency(command.currency)
        funding_account = await self._get_transfer_account(
            context.workspace.id,
            command.funding_account_id,
            currency,
        )
        return await self._create(
            context=context,
            plan=DebtCreationPlan(
                name=clean_required_text(command.name, "Debt name is required."),
                currency=currency,
                kind=DebtKind.LOAN_RECEIVABLE,
                initial_balance=ZERO,
                original_principal=amount,
                opened_on=command.opened_on,
                maturity_date=command.maturity_date,
                credit_limit=None,
                notes=command.notes,
                idempotency_key=command.idempotency_key,
                fingerprint=fingerprint,
                opening_transfer=DebtOpeningTransfer(
                    account=funding_account,
                    amount=amount,
                    operation_date=command.operation_date,
                    description=command.description,
                ),
            ),
        )

    async def take_loan(
        self,
        *,
        context: WorkspaceContext,
        command: TakeLoanCommand,
    ) -> Debt:
        fingerprint = DebtCommandFingerprint.calculate("take_loan", command)
        replay = await self._find_replay(context.workspace.id, command.idempotency_key, fingerprint)
        if replay is not None:
            return replay
        if command.kind not in {DebtKind.LOAN_PAYABLE, DebtKind.MORTGAGE}:
            raise DebtError("take_loan supports payable loans and mortgages only.")
        DebtPolicy.validate_terms(
            kind=command.kind,
            opening_balance=ZERO,
            opened_on=command.opened_on,
            maturity_date=command.maturity_date,
            original_principal=command.amount,
            credit_limit=None,
        )
        amount = normalize_positive_money(command.amount)
        currency = normalize_currency(command.currency)
        receiving_account = await self._get_transfer_account(
            context.workspace.id,
            command.receiving_account_id,
            currency,
        )
        return await self._create(
            context=context,
            plan=DebtCreationPlan(
                name=clean_required_text(command.name, "Debt name is required."),
                currency=currency,
                kind=command.kind,
                initial_balance=ZERO,
                original_principal=amount,
                opened_on=command.opened_on,
                maturity_date=command.maturity_date,
                credit_limit=None,
                notes=command.notes,
                idempotency_key=command.idempotency_key,
                fingerprint=fingerprint,
                opening_transfer=DebtOpeningTransfer(
                    account=receiving_account,
                    amount=amount,
                    operation_date=command.operation_date,
                    description=command.description,
                ),
            ),
        )

    async def open_credit_card(
        self,
        *,
        context: WorkspaceContext,
        command: OpenCreditCardCommand,
    ) -> Debt:
        fingerprint = DebtCommandFingerprint.calculate("open_credit_card", command)
        replay = await self._find_replay(context.workspace.id, command.idempotency_key, fingerprint)
        if replay is not None:
            return replay
        signed_balance = -command.opening_debt
        DebtPolicy.validate_terms(
            kind=DebtKind.CREDIT_CARD,
            opening_balance=signed_balance,
            opened_on=command.opened_on,
            maturity_date=None,
            original_principal=None,
            credit_limit=command.credit_limit,
        )
        signed_balance = DebtPolicy.ensure_balance(DebtKind.CREDIT_CARD, signed_balance)
        return await self._create(
            context=context,
            plan=DebtCreationPlan(
                name=clean_required_text(command.name, "Debt name is required."),
                currency=normalize_currency(command.currency),
                kind=DebtKind.CREDIT_CARD,
                initial_balance=signed_balance,
                original_principal=None,
                opened_on=command.opened_on,
                maturity_date=None,
                credit_limit=command.credit_limit.quantize(Decimal("0.01")),
                notes=command.notes,
                idempotency_key=command.idempotency_key,
                fingerprint=fingerprint,
            ),
        )

    async def _create(self, *, context: WorkspaceContext, plan: DebtCreationPlan) -> Debt:
        try:
            async with self.session.begin_nested():
                account = await self.accounts.create(
                    Account(
                        workspace_id=context.workspace.id,
                        name=plan.name,
                        type=AccountType.DEBT,
                        currency=plan.currency,
                        initial_balance=plan.initial_balance,
                        is_active=True,
                        notes=plan.notes,
                    )
                )
                debt = await self.debts.create(
                    Debt(
                        account_id=account.id,
                        workspace_id=context.workspace.id,
                        kind=plan.kind,
                        opened_on=plan.opened_on,
                        original_principal=plan.original_principal,
                        maturity_date=plan.maturity_date,
                        credit_limit=plan.credit_limit,
                        creation_idempotency_key=plan.idempotency_key,
                        creation_fingerprint=plan.fingerprint,
                    )
                )
                if plan.opening_transfer is not None:
                    transfer_category = await self.references.get_transfer_category(
                        context.workspace.id
                    )
                    if plan.kind is DebtKind.LOAN_RECEIVABLE:
                        source, destination = plan.opening_transfer.account, account
                    else:
                        source, destination = account, plan.opening_transfer.account
                    await self.posting.post_debt_transfer(
                        context=context,
                        source_account=source,
                        destination_account=destination,
                        amount=plan.opening_transfer.amount,
                        operation_date=plan.opening_transfer.operation_date,
                        description=plan.opening_transfer.description,
                        transfer_category=transfer_category,
                    )
                return debt
        except IntegrityError as error:
            replay = await self._find_replay(
                context.workspace.id,
                plan.idempotency_key,
                plan.fingerprint,
            )
            if replay is None:
                raise error
            return replay

    async def _find_replay(
        self,
        workspace_id: UUID,
        idempotency_key: UUID,
        fingerprint: str,
    ) -> Debt | None:
        debt = await self.debts.get_by_creation_idempotency_key(
            workspace_id,
            idempotency_key,
        )
        if debt is not None and debt.creation_fingerprint != fingerprint:
            raise DebtIdempotencyConflictError(
                "Idempotency key was reused with a different debt creation payload."
            )
        return debt

    async def _get_transfer_account(
        self,
        workspace_id: UUID,
        account_id: UUID,
        currency: str,
    ) -> Account:
        account = await self.accounts.get_for_workspace(workspace_id, account_id)
        if account is None or not account.is_active or account.type is AccountType.DEBT:
            raise DebtAccountUnavailableError(
                "Transfer account is not active or does not belong to this workspace."
            )
        if account.currency != currency:
            raise DebtCurrencyMismatchError("Debt and transfer account currencies must match.")
        return account
