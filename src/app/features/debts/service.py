from collections.abc import Awaitable
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.debts.creation import DebtCreator
from app.features.debts.lifecycle import DebtLifecycleManager
from app.features.debts.maintenance import DebtDeleter, DebtDetailsEditor, DeletedDebt
from app.features.debts.models import Debt, DebtPayment
from app.features.debts.payments import DebtPaymentRecorder, DebtPaymentReverser
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
        return await self._commit(mutation)

    async def add_existing_debt(
        self,
        *,
        context: WorkspaceContext,
        command: AddExistingDebtCommand,
    ) -> Debt:
        return await self._commit(self.creator.add_existing_debt(context=context, command=command))

    async def give_loan(
        self,
        *,
        context: WorkspaceContext,
        command: GiveLoanCommand,
    ) -> Debt:
        return await self._commit(self.creator.give_loan(context=context, command=command))

    async def take_loan(
        self,
        *,
        context: WorkspaceContext,
        command: TakeLoanCommand,
    ) -> Debt:
        return await self._commit(self.creator.take_loan(context=context, command=command))

    async def open_credit_card(
        self,
        *,
        context: WorkspaceContext,
        command: OpenCreditCardCommand,
    ) -> Debt:
        return await self._commit(self.creator.open_credit_card(context=context, command=command))

    async def record_payment(
        self,
        *,
        context: WorkspaceContext,
        command: RecordDebtPaymentCommand,
    ) -> DebtPayment:
        return await self._commit(self.payment_recorder.record(context=context, command=command))

    async def undo_payment(
        self,
        *,
        context: WorkspaceContext,
        command: UndoDebtPaymentCommand,
    ) -> DebtPayment:
        return await self._commit(self.payment_reverser.reverse(context=context, command=command))

    async def archive(
        self,
        *,
        context: WorkspaceContext,
        command: DebtLifecycleCommand,
    ) -> Debt:
        return await self._commit(self.lifecycle.archive(context=context, command=command))

    async def restore(
        self,
        *,
        context: WorkspaceContext,
        command: DebtLifecycleCommand,
    ) -> Debt:
        return await self._commit(self.lifecycle.restore(context=context, command=command))

    async def update(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateDebtCommand,
    ) -> Debt:
        return await self._commit(self.details_editor.update(context=context, command=command))

    async def delete(
        self,
        *,
        context: WorkspaceContext,
        command: DeleteDebtCommand,
    ) -> DeletedDebt:
        return await self._commit(self.deleter.delete(context=context, command=command))

    async def _commit(self, mutation: Awaitable[MutationResult]) -> MutationResult:
        try:
            debt = await mutation
            await self.session.commit()
            return debt
        except Exception:
            await self.session.rollback()
            raise
