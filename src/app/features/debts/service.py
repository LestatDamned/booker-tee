from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.debts.creation import DebtCreateOutcome, DebtCreator
from app.features.debts.lifecycle import DebtLifecycleManager
from app.features.debts.maintenance import DebtDeleter, DebtDetailsEditor, DeletedDebt
from app.features.debts.models import Debt, DebtPayment
from app.features.debts.payments import (
    DebtPaymentMutationOutcome,
    DebtPaymentRecorder,
    DebtPaymentReverser,
)
from app.features.debts.schemas import (
    AddExistingDebtCommand,
    DebtCreateCommand,
    DebtLifecycleCommand,
    DeleteDebtCommand,
    GiveLoanCommand,
    OpenCreditCardCommand,
    RecordDebtPaymentCommand,
    TakeLoanCommand,
    UndoDebtPaymentCommand,
    UpdateDebtCommand,
)
from app.features.workspaces.activity_repository import WorkspaceActivityRepository
from app.features.workspaces.application.activity_details import (
    DebtArchivedActivityDetails,
    DebtCreatedActivityDetails,
    DebtDeletedActivityDetails,
    DebtPaymentRecordedActivityDetails,
    DebtPaymentUndoneActivityDetails,
    DebtRestoredActivityDetails,
    DebtUpdatedActivityDetails,
)
from app.features.workspaces.application.activity_writer import WorkspaceActivityWriter
from app.features.workspaces.service import WorkspaceContext

MutationResult = TypeVar("MutationResult")


class DebtService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.creator = DebtCreator(session)
        self.payment_recorder = DebtPaymentRecorder(session)
        self.payment_reverser = DebtPaymentReverser(session)
        self.lifecycle = DebtLifecycleManager(session)
        self.details_editor = DebtDetailsEditor(session)
        self.deleter = DebtDeleter(session)
        self.activity = WorkspaceActivityWriter(WorkspaceActivityRepository(session))

    async def create(
        self,
        *,
        context: WorkspaceContext,
        command: DebtCreateCommand,
    ) -> Debt:
        if isinstance(command, AddExistingDebtCommand):
            mutation = self.creator.add_existing_debt(context=context, command=command)
        elif isinstance(command, GiveLoanCommand):
            mutation = self.creator.give_loan(context=context, command=command)
        elif isinstance(command, TakeLoanCommand):
            mutation = self.creator.take_loan(context=context, command=command)
        else:
            mutation = self.creator.open_credit_card(context=context, command=command)
        return await self._create(context=context, command=command, mutation=mutation)

    async def add_existing_debt(
        self,
        *,
        context: WorkspaceContext,
        command: AddExistingDebtCommand,
    ) -> Debt:
        return await self._create(
            context=context,
            command=command,
            mutation=self.creator.add_existing_debt(context=context, command=command),
        )

    async def give_loan(
        self,
        *,
        context: WorkspaceContext,
        command: GiveLoanCommand,
    ) -> Debt:
        return await self._create(
            context=context,
            command=command,
            mutation=self.creator.give_loan(context=context, command=command),
        )

    async def take_loan(
        self,
        *,
        context: WorkspaceContext,
        command: TakeLoanCommand,
    ) -> Debt:
        return await self._create(
            context=context,
            command=command,
            mutation=self.creator.take_loan(context=context, command=command),
        )

    async def open_credit_card(
        self,
        *,
        context: WorkspaceContext,
        command: OpenCreditCardCommand,
    ) -> Debt:
        return await self._create(
            context=context,
            command=command,
            mutation=self.creator.open_credit_card(context=context, command=command),
        )

    async def record_payment(
        self,
        *,
        context: WorkspaceContext,
        command: RecordDebtPaymentCommand,
    ) -> DebtPayment:
        outcome = await self._commit(
            self.payment_recorder.record(context=context, command=command),
            after=lambda result: self._record_payment(context, result),
        )
        return outcome.payment

    async def undo_payment(
        self,
        *,
        context: WorkspaceContext,
        command: UndoDebtPaymentCommand,
    ) -> DebtPayment:
        outcome = await self._commit(
            self.payment_reverser.reverse(context=context, command=command),
            after=lambda result: self._record_payment_undo(context, result),
        )
        return outcome.payment

    async def archive(
        self,
        *,
        context: WorkspaceContext,
        command: DebtLifecycleCommand,
    ) -> Debt:
        return await self._commit(
            self.lifecycle.archive(context=context, command=command),
            after=lambda debt: self.activity.debt_archived(
                context=context,
                debt_account_id=debt.account_id,
                details=DebtArchivedActivityDetails(),
            ),
        )

    async def restore(
        self,
        *,
        context: WorkspaceContext,
        command: DebtLifecycleCommand,
    ) -> Debt:
        return await self._commit(
            self.lifecycle.restore(context=context, command=command),
            after=lambda debt: self.activity.debt_restored(
                context=context,
                debt_account_id=debt.account_id,
                details=DebtRestoredActivityDetails(),
            ),
        )

    async def update(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateDebtCommand,
    ) -> Debt:
        return await self._commit(
            self.details_editor.update(context=context, command=command),
            after=lambda debt: self.activity.debt_updated(
                context=context,
                debt_account_id=debt.account_id,
                details=DebtUpdatedActivityDetails(
                    display_label=_activity_label(command.name),
                ),
            ),
        )

    async def delete(
        self,
        *,
        context: WorkspaceContext,
        command: DeleteDebtCommand,
    ) -> DeletedDebt:
        return await self._commit(
            self.deleter.delete(context=context, command=command),
            after=lambda deleted: self.activity.debt_deleted(
                context=context,
                debt_account_id=deleted.account_id,
                details=DebtDeletedActivityDetails(
                    display_label=_activity_label(deleted.name),
                ),
            ),
        )

    async def _commit(
        self,
        mutation: Awaitable[MutationResult],
        *,
        after: Callable[[MutationResult], Awaitable[None]] | None = None,
    ) -> MutationResult:
        try:
            result = await mutation
            if after is not None:
                await after(result)
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise

    async def _create(
        self,
        *,
        context: WorkspaceContext,
        command: DebtCreateCommand,
        mutation: Awaitable[DebtCreateOutcome],
    ) -> Debt:
        outcome = await self._commit(
            mutation,
            after=lambda result: self._record_created(context, command, result),
        )
        return outcome.debt

    async def _record_created(
        self,
        context: WorkspaceContext,
        command: DebtCreateCommand,
        outcome: DebtCreateOutcome,
    ) -> None:
        if outcome.replayed:
            return
        await self.activity.debt_created(
            context=context,
            debt_account_id=outcome.debt.account_id,
            details=DebtCreatedActivityDetails(
                display_label=_activity_label(command.name),
                debt_kind=outcome.debt.kind,
            ),
        )

    async def _record_payment(
        self,
        context: WorkspaceContext,
        outcome: DebtPaymentMutationOutcome,
    ) -> None:
        if outcome.replayed:
            return
        await self.activity.debt_payment_recorded(
            context=context,
            debt_account_id=outcome.payment.debt_account_id,
            details=DebtPaymentRecordedActivityDetails(payment_id=outcome.payment.id),
        )

    async def _record_payment_undo(
        self,
        context: WorkspaceContext,
        outcome: DebtPaymentMutationOutcome,
    ) -> None:
        if outcome.replayed:
            return
        await self.activity.debt_payment_undone(
            context=context,
            debt_account_id=outcome.payment.debt_account_id,
            details=DebtPaymentUndoneActivityDetails(payment_id=outcome.payment.id),
        )


def _activity_label(value: str) -> str:
    return " ".join(value.split())[:160]
