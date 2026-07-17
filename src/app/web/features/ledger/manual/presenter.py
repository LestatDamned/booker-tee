from datetime import date
from typing import Final
from urllib.parse import urlencode
from uuid import UUID

from app.features.ledger.application.listing import LedgerPage, ManualOperationFilters
from app.features.ledger.mapping.dto import ManualOperationView, OperationRefMoneyEntryView
from app.features.ledger.models import OperationStatus, OperationType
from app.web.features.ledger.manual.view_models import (
    BadgeTone,
    ManualLedgerFilterOptionVM,
    ManualLedgerFiltersVM,
    ManualLedgerMetaVM,
    ManualLedgerPageVM,
    ManualLedgerRowVM,
)
from app.web.ui.actions import ActionSetVM, LinkActionVM
from app.web.ui.money import EntryDirection, MoneyFormatter, MoneyValueVM, OperationTone

MANUAL_LEDGER_URL: Final = "/_next/ledger/manual"
PER_PAGE_OPTIONS: Final = (25, 50, 100, 200)

OPERATION_LABELS: Final[dict[OperationType, str]] = {
    OperationType.INCOME: "доход",
    OperationType.EXPENSE: "расход",
    OperationType.TRANSFER: "перевод",
    OperationType.ADJUSTMENT: "корректировка",
}
OPERATION_TONES: Final[dict[OperationType, OperationTone]] = {
    OperationType.INCOME: "income",
    OperationType.EXPENSE: "expense",
    OperationType.TRANSFER: "transfer",
    OperationType.ADJUSTMENT: "adjustment",
}
ENTRY_DIRECTIONS: Final[dict[OperationType, EntryDirection | None]] = {
    OperationType.INCOME: "inflow",
    OperationType.EXPENSE: "outflow",
    OperationType.TRANSFER: None,
    OperationType.ADJUSTMENT: None,
}
STATUS_PRESENTATION: Final[dict[OperationStatus, tuple[str, BadgeTone]]] = {
    OperationStatus.DRAFT: ("черновик", "warning"),
    OperationStatus.NEEDS_REVIEW: ("нужна проверка", "warning"),
    OperationStatus.CONFIRMED: ("подтверждено", "success"),
    OperationStatus.IGNORED: ("отменено", "neutral"),
    OperationStatus.DUPLICATE: ("дубликат", "danger"),
}


class ManualLedgerPresenter:
    def present(
        self,
        *,
        workspace_name: str,
        operations: list[ManualOperationView],
        page: LedgerPage,
        filters: ManualOperationFilters,
        focused_operation_id: UUID | None,
        can_write: bool,
    ) -> ManualLedgerPageVM:
        filters_vm = self._filters(filters, page)
        return ManualLedgerPageVM(
            workspace_name=workspace_name,
            total_label=self._total_label(page.total),
            readonly_message=self._readonly_message(can_write),
            rows=tuple(
                self._row(
                    operation,
                    focused_operation_id=focused_operation_id,
                    can_write=can_write,
                )
                for operation in operations
            ),
            filters=filters_vm,
            show_pagination=page.total_pages > 1,
            page_label=f"Страница {page.page} из {page.total_pages}",
            previous_url=self._page_url(
                filters,
                page=page.previous_page,
                per_page=page.per_page,
                focused_operation_id=focused_operation_id,
            )
            if page.has_previous
            else None,
            next_url=self._page_url(
                filters,
                page=page.next_page,
                per_page=page.per_page,
                focused_operation_id=focused_operation_id,
            )
            if page.has_next
            else None,
            empty_title=(
                "По этим фильтрам операций нет" if filters_vm.active else "Ручных операций пока нет"
            ),
            empty_description=(
                "Измените условия поиска или сбросьте фильтры."
                if filters_vm.active
                else "Ручные операции появятся здесь после создания в рабочем интерфейсе."
            ),
        )

    def _row(
        self,
        operation: ManualOperationView,
        *,
        focused_operation_id: UUID | None,
        can_write: bool,
    ) -> ManualLedgerRowVM:
        status_label, status_tone = STATUS_PRESENTATION[operation.status]
        return ManualLedgerRowVM(
            id=f"next-operation-{operation.id}",
            operation_id=operation.id,
            description=operation.description or "Без описания",
            date_label=self._date_label(operation.operation_date),
            money=self._money(operation),
            operation_label=OPERATION_LABELS[operation.type],
            operation_tone=OPERATION_TONES[operation.type],
            status_label=status_label,
            status_tone=status_tone,
            meta=self._meta(operation),
            actions=self._actions(operation, can_write=can_write),
            is_targeted=focused_operation_id == operation.id,
            is_inactive=operation.status == OperationStatus.IGNORED,
        )

    def _money(self, operation: ManualOperationView) -> MoneyValueVM | None:
        if operation.edit_amount is None:
            return None
        return MoneyFormatter.format(
            operation.edit_amount,
            self._currency(operation),
            operation_type=OPERATION_TONES[operation.type],
            entry_direction=ENTRY_DIRECTIONS[operation.type],
        )

    def _meta(self, operation: ManualOperationView) -> tuple[ManualLedgerMetaVM, ...]:
        if operation.type == OperationType.TRANSFER:
            return (ManualLedgerMetaVM(self._transfer_route(operation)),)

        meta: list[ManualLedgerMetaVM] = []
        if operation.category is None:
            meta.append(ManualLedgerMetaVM("без категории", "warning"))
        else:
            meta.append(ManualLedgerMetaVM(operation.category.name))
        if operation.property is not None:
            meta.append(ManualLedgerMetaVM(operation.property.name))
        if operation.primary_entry is not None:
            meta.append(ManualLedgerMetaVM(self._account_name(operation.primary_entry)))
        return tuple(meta)

    def _actions(self, operation: ManualOperationView, *, can_write: bool) -> ActionSetVM:
        legacy_url = f"/ledger/manual?operation_id={operation.id}#operation-{operation.id}"
        action = LinkActionVM(
            label=(
                "Изменить в текущем интерфейсе"
                if can_write and operation.status != OperationStatus.IGNORED
                else "Открыть текущую версию"
            ),
            url=legacy_url,
            icon="source",
        )
        if can_write and operation.status != OperationStatus.IGNORED:
            return ActionSetVM(primary=action)
        return ActionSetVM(secondary=(action,))

    def _filters(
        self,
        filters: ManualOperationFilters,
        page: LedgerPage,
    ) -> ManualLedgerFiltersVM:
        active = bool(
            filters.date_from
            or filters.date_to
            or filters.operation_type
            or filters.status
            or filters.search
        )
        return ManualLedgerFiltersVM(
            date_from=filters.date_from.isoformat() if filters.date_from else "",
            date_to=filters.date_to.isoformat() if filters.date_to else "",
            search=filters.search or "",
            operation_types=tuple(
                ManualLedgerFilterOptionVM(
                    value=operation_type.value,
                    label=OPERATION_LABELS[operation_type],
                    selected=filters.operation_type == operation_type,
                )
                for operation_type in OperationType
            ),
            statuses=tuple(
                ManualLedgerFilterOptionVM(
                    value=operation_status.value,
                    label=STATUS_PRESENTATION[operation_status][0],
                    selected=filters.status == operation_status,
                )
                for operation_status in OperationStatus
            ),
            per_page=page.per_page,
            per_page_options=PER_PAGE_OPTIONS,
            active=active,
            reset_url=MANUAL_LEDGER_URL,
        )

    def _page_url(
        self,
        filters: ManualOperationFilters,
        *,
        page: int,
        per_page: int,
        focused_operation_id: UUID | None,
    ) -> str:
        query: dict[str, str | int] = {"page": page, "per_page": per_page}
        optional_values = {
            "date_from": filters.date_from.isoformat() if filters.date_from else None,
            "date_to": filters.date_to.isoformat() if filters.date_to else None,
            "type": filters.operation_type.value if filters.operation_type else None,
            "status": filters.status.value if filters.status else None,
            "search": filters.search,
            "operation_id": str(focused_operation_id) if focused_operation_id else None,
        }
        query.update({name: value for name, value in optional_values.items() if value})
        return f"{MANUAL_LEDGER_URL}?{urlencode(query)}"

    def _currency(self, operation: ManualOperationView) -> str:
        entry = (
            operation.source_entry
            if operation.type == OperationType.TRANSFER
            else operation.primary_entry
        )
        if entry is None or entry.account is None:
            return ""
        return entry.account.currency

    def _transfer_route(self, operation: ManualOperationView) -> str:
        return (
            f"{self._account_name(operation.source_entry)}"
            f" → {self._account_name(operation.destination_entry)}"
        )

    def _account_name(self, entry: OperationRefMoneyEntryView | None) -> str:
        if entry is None or entry.account is None:
            return "счёт не найден"
        return entry.account.name

    def _readonly_message(self, can_write: bool) -> str:
        if can_write:
            return (
                "Первый срез Frontend Next доступен только для просмотра. "
                "Изменение пока открывается в текущем интерфейсе."
            )
        return "Ручные операции доступны только для просмотра согласно вашей роли."

    def _total_label(self, total: int) -> str:
        remainder_100 = total % 100
        remainder_10 = total % 10
        if remainder_10 == 1 and remainder_100 != 11:
            noun = "ручная операция"
        elif remainder_10 in {2, 3, 4} and remainder_100 not in {12, 13, 14}:
            noun = "ручные операции"
        else:
            noun = "ручных операций"
        return f"{total} {noun}"

    def _date_label(self, value: date) -> str:
        return value.strftime("%d.%m.%Y")
