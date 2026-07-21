from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.ledger.application.manual_contracts import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
    UpdateManualOperationCommand,
    UpdateManualTransferCommand,
)
from app.features.ledger.domain.money import (
    TransferAmounts,
    affects_profit_for_operation_type,
    ensure_same_currency,
    manual_income_expense_amount,
)
from app.features.ledger.domain.text import clean_description
from app.features.ledger.domain.types import (
    OperationSource,
    OperationStatus,
    OperationType,
    manual_operation_actions,
)
from app.features.ledger.errors import (
    LedgerPostingError,
    ManualOperationLifecycleConflictError,
    ManualOperationNotEditableError,
    ManualOperationNotFoundError,
    OperationIdempotencyConflictError,
    OperationVersionConflictError,
)
from app.features.ledger.mapping.operations import (
    build_manual_income_expense_operation,
    build_manual_transfer_operation,
    build_money_entry,
    manual_income_expense_fingerprint,
    manual_transfer_fingerprint,
)
from app.features.ledger.models import MoneyEntry, Operation
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.service import WorkspaceContext


class ManualOperationWriter:
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
        fingerprint = manual_income_expense_fingerprint(command)
        try:
            replay = await self._find_idempotent_replay(
                workspace_id=context.workspace.id,
                idempotency_key=command.idempotency_key,
                fingerprint=fingerprint,
            )
            if replay is not None:
                return replay
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
        except IntegrityError as error:
            return await self._recover_idempotent_race(
                workspace_id=context.workspace.id,
                idempotency_key=command.idempotency_key,
                fingerprint=fingerprint,
                integrity_error=error,
            )
        except Exception:
            await self.session.rollback()
            raise

    async def create_transfer(
        self,
        *,
        context: WorkspaceContext,
        command: CreateManualTransferCommand,
    ) -> Operation:
        fingerprint = manual_transfer_fingerprint(command)
        try:
            replay = await self._find_idempotent_replay(
                workspace_id=context.workspace.id,
                idempotency_key=command.idempotency_key,
                fingerprint=fingerprint,
            )
            if replay is not None:
                return replay
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
        except IntegrityError as error:
            return await self._recover_idempotent_race(
                workspace_id=context.workspace.id,
                idempotency_key=command.idempotency_key,
                fingerprint=fingerprint,
                integrity_error=error,
            )
        except Exception:
            await self.session.rollback()
            raise

    async def _find_idempotent_replay(
        self,
        *,
        workspace_id: UUID,
        idempotency_key: UUID | None,
        fingerprint: str,
    ) -> Operation | None:
        if idempotency_key is None:
            return None
        operation = await self.ledger.get_operation_by_idempotency_key(
            workspace_id=workspace_id,
            idempotency_key=idempotency_key,
        )
        if operation is None:
            return None
        if operation.idempotency_fingerprint != fingerprint:
            raise OperationIdempotencyConflictError()
        return operation

    async def _recover_idempotent_race(
        self,
        *,
        workspace_id: UUID,
        idempotency_key: UUID | None,
        fingerprint: str,
        integrity_error: IntegrityError,
    ) -> Operation:
        await self.session.rollback()
        replay = await self._find_idempotent_replay(
            workspace_id=workspace_id,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        if replay is None:
            raise integrity_error
        return replay

    async def update(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateManualOperationCommand,
    ) -> Operation:
        try:
            operation = await self._get_manual_operation(context.workspace.id, command.operation_id)
            if not manual_operation_actions(operation.status).can_edit:
                raise ManualOperationNotEditableError()
            self._ensure_expected_version(operation, command.expected_version)
            operation.description = clean_description(command.description)
            operation.operation_date = command.operation_date
            operation.updated_by_user_id = context.user.id

            if isinstance(command, UpdateManualTransferCommand):
                operation.type = OperationType.TRANSFER
                operation.affects_profit = affects_profit_for_operation_type(OperationType.TRANSFER)
                await self._update_as_transfer(
                    context=context,
                    operation=operation,
                    source_account_id=command.source_account_id,
                    destination_account_id=command.destination_account_id,
                    amount=command.amount,
                )
            else:
                operation.type = command.operation_type
                operation.affects_profit = affects_profit_for_operation_type(command.operation_type)
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
        except StaleDataError as error:
            await self.session.rollback()
            raise OperationVersionConflictError() from error
        except Exception:
            await self.session.rollback()
            raise

    async def cancel(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int | None = None,
    ) -> Operation:
        operation = await self._get_manual_operation(context.workspace.id, operation_id)
        self._ensure_expected_version(operation, expected_version)
        if not manual_operation_actions(operation.status).can_cancel:
            raise ManualOperationLifecycleConflictError(
                "Only confirmed manual operations can be cancelled."
            )
        operation.status = OperationStatus.IGNORED
        operation.updated_by_user_id = context.user.id
        await self._commit_versioned()
        return operation

    async def restore(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int | None = None,
    ) -> Operation:
        operation = await self._get_manual_operation(context.workspace.id, operation_id)
        self._ensure_expected_version(operation, expected_version)
        if not manual_operation_actions(operation.status).can_restore:
            raise ManualOperationLifecycleConflictError(
                "Only cancelled manual operations can be restored."
            )
        operation.status = OperationStatus.CONFIRMED
        operation.updated_by_user_id = context.user.id
        await self._commit_versioned()
        return operation

    async def delete(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int | None = None,
    ) -> None:
        operation = await self._get_manual_operation(context.workspace.id, operation_id)
        self._ensure_expected_version(operation, expected_version)
        if not manual_operation_actions(operation.status).can_delete:
            raise ManualOperationLifecycleConflictError(
                "Cancel a manual operation before deleting it."
            )
        await self.ledger.delete_operation(operation)
        await self._commit_versioned()

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
        operation.category = transfer_category
        operation.property = None
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
        operation.category = category
        operation.property = property_
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
            raise ManualOperationNotFoundError()
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
        operation.money_entries.extend(money_entries)

    def _ensure_expected_version(
        self,
        operation: Operation,
        expected_version: int | None,
    ) -> None:
        if expected_version is not None and operation.version != expected_version:
            raise OperationVersionConflictError()

    async def _commit_versioned(self) -> None:
        try:
            await self.session.commit()
        except StaleDataError as error:
            await self.session.rollback()
            raise OperationVersionConflictError() from error
