from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.ledger.application.commands import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
    UpdateManualOperationCommand,
)
from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.ledger.domain import (
    TransferAmounts,
    affects_profit_for_operation_type,
    ensure_same_currency,
    manual_income_expense_amount,
    require_uuid,
)
from app.features.ledger.domain.text import clean_description
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.mapping.operation_factory import (
    build_manual_income_expense_operation,
    build_manual_transfer_operation,
    build_money_entry,
)
from app.features.ledger.models import (
    MoneyEntry,
    Operation,
    OperationSource,
    OperationStatus,
    OperationType,
)
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.service import WorkspaceContext


class ManualOperationUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ledger = LedgerRepository(session)
        self.references = LedgerReferenceResolver(session)

    async def create_income_expense(
        self,
        *,
        context: WorkspaceContext,
        command: CreateManualIncomeExpenseCommand,
    ) -> Operation:
        try:
            if command.operation_type not in {OperationType.INCOME, OperationType.EXPENSE}:
                raise LedgerPostingError("Manual operation must be income or expense.")
            account = await self.references.get_account(context.workspace.id, command.account_id)
            signed_amount = manual_income_expense_amount(
                command.operation_type,
                command.amount,
            )
            category = await self.references.get_category_or_uncategorized(
                context.workspace.id,
                command.category_id,
            )
            property_ = await self.references.get_property(
                context.workspace.id,
                command.property_id,
            )
            operation = await self.ledger.create_operation(
                build_manual_income_expense_operation(
                    context=context,
                    command=command,
                    category=category,
                    property_=property_,
                )
            )
            await self.ledger.create_money_entry(
                build_money_entry(
                    context=context,
                    operation=operation,
                    account=account,
                    amount=signed_amount,
                    entry_order=1,
                )
            )
            await self.session.commit()
            return operation
        except Exception:
            await self.session.rollback()
            raise

    async def create_transfer(
        self,
        *,
        context: WorkspaceContext,
        command: CreateManualTransferCommand,
    ) -> Operation:
        try:
            source_account = await self.references.get_account(
                context.workspace.id,
                command.source_account_id,
            )
            destination_account = await self.references.get_account(
                context.workspace.id,
                command.destination_account_id,
            )
            amounts = TransferAmounts.for_manual_transfer(
                source_account_id=source_account.id,
                destination_account_id=destination_account.id,
                amount=command.amount,
            )
            ensure_same_currency(source_account, destination_account)
            transfer_category = await self.references.get_transfer_category(context.workspace.id)
            operation = await self.ledger.create_operation(
                build_manual_transfer_operation(
                    context=context,
                    command=command,
                    transfer_category=transfer_category,
                )
            )
            await self.ledger.create_money_entry(
                build_money_entry(
                    context=context,
                    operation=operation,
                    account=source_account,
                    amount=amounts.source_amount,
                    entry_order=1,
                )
            )
            await self.ledger.create_money_entry(
                build_money_entry(
                    context=context,
                    operation=operation,
                    account=destination_account,
                    amount=amounts.destination_amount,
                    entry_order=2,
                )
            )
            await self.session.commit()
            return operation
        except Exception:
            await self.session.rollback()
            raise

    async def update(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateManualOperationCommand,
    ) -> Operation:
        try:
            operation = await self._get_manual_operation(context.workspace.id, command.operation_id)
            operation.type = command.operation_type
            operation.affects_profit = affects_profit_for_operation_type(command.operation_type)
            operation.description = clean_description(command.description)
            operation.operation_date = command.operation_date
            operation.updated_by_user_id = context.user.id

            if command.operation_type == OperationType.TRANSFER:
                await self._update_as_transfer(
                    context=context,
                    operation=operation,
                    source_account_id=command.account_id,
                    destination_account_id=require_uuid(
                        command.destination_account_id,
                        "Destination account is required.",
                    ),
                    amount=command.amount,
                )
            else:
                await self._update_as_income_expense(
                    context=context,
                    operation=operation,
                    operation_type=command.operation_type,
                    account_id=command.account_id,
                    amount=command.amount,
                    category_id=command.category_id,
                    property_id=command.property_id,
                )

            await self.session.commit()
            return operation
        except Exception:
            await self.session.rollback()
            raise

    async def cancel(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
    ) -> Operation:
        operation = await self._get_manual_operation(context.workspace.id, operation_id)
        if operation.status != OperationStatus.CONFIRMED:
            raise LedgerPostingError("Only confirmed manual operations can be cancelled.")
        operation.status = OperationStatus.IGNORED
        operation.updated_by_user_id = context.user.id
        await self.session.commit()
        return operation

    async def restore(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
    ) -> Operation:
        operation = await self._get_manual_operation(context.workspace.id, operation_id)
        if operation.status != OperationStatus.IGNORED:
            raise LedgerPostingError("Only cancelled manual operations can be restored.")
        operation.status = OperationStatus.CONFIRMED
        operation.updated_by_user_id = context.user.id
        await self.session.commit()
        return operation

    async def delete(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
    ) -> None:
        operation = await self._get_manual_operation(context.workspace.id, operation_id)
        if operation.status not in {OperationStatus.DRAFT, OperationStatus.IGNORED}:
            raise LedgerPostingError("Cancel a manual operation before deleting it.")
        await self.ledger.delete_operation(operation)
        await self.session.commit()

    async def _update_as_transfer(
        self,
        *,
        context: WorkspaceContext,
        operation: Operation,
        source_account_id: UUID,
        destination_account_id: UUID,
        amount: Decimal,
    ) -> None:
        source_account = await self.references.get_account(context.workspace.id, source_account_id)
        destination_account = await self.references.get_account(
            context.workspace.id,
            destination_account_id,
        )
        ensure_same_currency(source_account, destination_account)
        transfer_category = await self.references.get_transfer_category(context.workspace.id)
        transfer_amounts = TransferAmounts.for_manual_transfer(
            source_account_id=source_account.id,
            destination_account_id=destination_account.id,
            amount=amount,
        )
        operation.category_id = transfer_category.id
        operation.property_id = None
        await self._replace_money_entries(
            operation,
            [
                build_money_entry(
                    context=context,
                    operation=operation,
                    account=source_account,
                    amount=transfer_amounts.source_amount,
                    entry_order=1,
                ),
                build_money_entry(
                    context=context,
                    operation=operation,
                    account=destination_account,
                    amount=transfer_amounts.destination_amount,
                    entry_order=2,
                ),
            ],
        )

    async def _update_as_income_expense(
        self,
        *,
        context: WorkspaceContext,
        operation: Operation,
        operation_type: OperationType,
        account_id: UUID,
        amount: Decimal,
        category_id: UUID | None,
        property_id: UUID | None,
    ) -> None:
        if operation_type not in {OperationType.INCOME, OperationType.EXPENSE}:
            raise LedgerPostingError("Manual operation must be income, expense, or transfer.")
        account = await self.references.get_account(context.workspace.id, account_id)
        category = await self.references.get_category_or_uncategorized(
            context.workspace.id,
            category_id,
        )
        property_ = await self.references.get_property(context.workspace.id, property_id)
        operation.category_id = category.id
        operation.property_id = property_.id if property_ else None
        await self._replace_money_entries(
            operation,
            [
                build_money_entry(
                    context=context,
                    operation=operation,
                    account=account,
                    amount=manual_income_expense_amount(operation_type, amount),
                    entry_order=1,
                )
            ],
        )

    async def _get_manual_operation(self, workspace_id: UUID, operation_id: UUID) -> Operation:
        operation = await self.ledger.get_operation_for_workspace(workspace_id, operation_id)
        if operation is None:
            raise LedgerPostingError("Manual operation was not found.")
        if operation.source != OperationSource.MANUAL:
            raise LedgerPostingError("Only manual operations can be changed here.")
        return operation

    async def _replace_money_entries(
        self,
        operation: Operation,
        money_entries: list[MoneyEntry],
    ) -> None:
        for money_entry in list(operation.money_entries):
            await self.session.delete(money_entry)
        operation.money_entries.clear()
        await self.session.flush()
        for money_entry in money_entries:
            await self.ledger.create_money_entry(money_entry)
