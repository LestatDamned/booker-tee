from uuid import UUID

from app.features.ledger.application.listing import LedgerPage, ManualOperationFilters
from app.features.ledger.mapping.dto import ManualOperationView, OperationRefMoneyEntryView
from app.features.ledger.models import OperationStatus, OperationType
from app.features.ledger.presentation.manual_operations.models import (
    ManualOperationActionVM,
    ManualOperationDrawerVM,
    ManualOperationMetaVM,
    ManualOperationRowVM,
    ManualOperationsPageVM,
)
from app.templating import date_ru, ru_label


class ManualOperationsPresenter:
    def build_page(
        self,
        *,
        operations: list[ManualOperationView],
        page: LedgerPage,
        filters: ManualOperationFilters,
        focused_operation_id: UUID | None,
        can_write: bool,
    ) -> ManualOperationsPageVM:
        return ManualOperationsPageVM(
            total_label=f"{page.total} ручных операций",
            filters_active=self._filters_active(filters, focused_operation_id),
            rows=[
                self._build_row(
                    operation,
                    focused_operation_id=focused_operation_id,
                    can_write=can_write,
                )
                for operation in operations
            ],
            page=page,
        )

    def _build_row(
        self,
        operation: ManualOperationView,
        *,
        focused_operation_id: UUID | None,
        can_write: bool,
    ) -> ManualOperationRowVM:
        return ManualOperationRowVM(
            id=f"operation-{operation.id}",
            operation_id=operation.id,
            tone=operation.type.value,
            status=operation.status,
            operation_type=operation.type,
            date_label=date_ru(operation.operation_date),
            amount=operation.edit_amount,
            amount_direction=self._amount_direction(operation),
            currency=self._display_currency(operation),
            description=operation.description or "Без описания",
            meta=self._meta(operation),
            is_current=focused_operation_id == operation.id,
            is_inactive=operation.status == OperationStatus.IGNORED,
            drawer=self._drawer(operation),
            lifecycle_actions=self._lifecycle_actions(operation, can_write=can_write),
            danger_actions=self._danger_actions(operation, can_write=can_write),
        )

    def _meta(self, operation: ManualOperationView) -> list[ManualOperationMetaVM]:
        meta: list[ManualOperationMetaVM] = []
        if operation.type == OperationType.TRANSFER:
            meta.extend(
                [
                    ManualOperationMetaVM(f"из {self._account_name(operation.source_entry)}"),
                    ManualOperationMetaVM(f"в {self._account_name(operation.destination_entry)}"),
                ]
            )
        elif operation.primary_entry is not None:
            direction = "на счет" if operation.primary_entry.amount > 0 else "со счета"
            meta.append(
                ManualOperationMetaVM(f"{direction} {self._account_name(operation.primary_entry)}")
            )

        if operation.category is not None:
            meta.append(
                ManualOperationMetaVM(operation.category.name, operation.category.kind.value)
            )
        if operation.property is not None:
            meta.append(ManualOperationMetaVM(operation.property.name))
        meta.append(ManualOperationMetaVM(ru_label(operation.status)))
        return meta

    def _drawer(self, operation: ManualOperationView) -> ManualOperationDrawerVM:
        return ManualOperationDrawerVM(
            form_id=f"manual-operation-form-{operation.id}",
            form_action=f"/ledger/manual/{operation.id}",
            operation_type=operation.type,
            operation_date=date_ru(operation.operation_date),
            amount=operation.edit_amount,
            account_id=self._selected_account_id(operation),
            destination_account_id=self._selected_destination_account_id(operation),
            category_id=operation.category_id,
            property_id=operation.property_id,
            description=operation.description or "",
        )

    def _lifecycle_actions(
        self,
        operation: ManualOperationView,
        *,
        can_write: bool,
    ) -> list[ManualOperationActionVM]:
        if not can_write:
            return []
        if operation.status == OperationStatus.CONFIRMED:
            return [
                ManualOperationActionVM(
                    label="отменить",
                    icon="rotate-ccw",
                    form_action=f"/ledger/manual/{operation.id}/cancel",
                )
            ]
        if operation.status == OperationStatus.IGNORED:
            return [
                ManualOperationActionVM(
                    label="восстановить",
                    icon="rotate-ccw",
                    form_action=f"/ledger/manual/{operation.id}/restore",
                )
            ]
        return []

    def _danger_actions(
        self,
        operation: ManualOperationView,
        *,
        can_write: bool,
    ) -> list[ManualOperationActionVM]:
        if not can_write or operation.status != OperationStatus.IGNORED:
            return []
        return [
            ManualOperationActionVM(
                label="удалить",
                icon="trash",
                form_action=f"/ledger/manual/{operation.id}/delete",
                variant="danger",
            )
        ]

    def _display_currency(self, operation: ManualOperationView) -> str:
        if operation.type == OperationType.TRANSFER:
            return self._entry_currency(operation.source_entry)
        return self._entry_currency(operation.primary_entry)

    def _amount_direction(self, operation: ManualOperationView) -> str:
        if operation.type == OperationType.INCOME:
            return "income"
        if operation.type == OperationType.EXPENSE:
            return "expense"
        return "transfer"

    def _selected_account_id(self, operation: ManualOperationView) -> UUID | None:
        if operation.type == OperationType.TRANSFER:
            return operation.source_entry.account_id if operation.source_entry else None
        return operation.primary_entry.account_id if operation.primary_entry else None

    def _selected_destination_account_id(self, operation: ManualOperationView) -> UUID | None:
        if operation.destination_entry is None:
            return None
        return operation.destination_entry.account_id

    def _filters_active(
        self,
        filters: ManualOperationFilters,
        focused_operation_id: UUID | None,
    ) -> bool:
        return bool(
            filters.date_from
            or filters.date_to
            or filters.operation_type
            or filters.status
            or filters.account_id
            or filters.category_id
            or filters.property_id
            or filters.search
            or focused_operation_id
        )

    def _entry_currency(self, entry: OperationRefMoneyEntryView | None) -> str:
        if entry is None or entry.account is None:
            return ""
        return entry.account.currency

    def _account_name(self, entry: OperationRefMoneyEntryView | None) -> str:
        if entry is None or entry.account is None:
            return "счет не найден"
        return entry.account.name
