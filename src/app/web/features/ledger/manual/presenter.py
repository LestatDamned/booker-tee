from collections.abc import Iterable
from datetime import date
from typing import Final
from urllib.parse import urlencode
from uuid import UUID

from app.features.ledger.application.listing import LedgerPage, ManualOperationFilters
from app.features.ledger.mapping.dto import ManualOperationView, OperationRefMoneyEntryView
from app.features.ledger.models import OperationStatus, OperationType
from app.web.features.ledger.manual.action_policy import ManualOperationActionPolicy
from app.web.features.ledger.manual.queries import ManualLedgerReferenceData
from app.web.features.ledger.manual.query_state import (
    MANUAL_LEDGER_URL,
    ManualLedgerPageParams,
)
from app.web.features.ledger.manual.view_models import (
    BadgeTone,
    ManualLedgerCreateRegionVM,
    ManualLedgerEditPanelVM,
    ManualLedgerFilterOptionVM,
    ManualLedgerFiltersVM,
    ManualLedgerFormVM,
    ManualLedgerMetaVM,
    ManualLedgerPageVM,
    ManualLedgerRowVM,
)
from app.web.ui.actions import DisclosureActionVM
from app.web.ui.money import EntryDirection, MoneyFormatter, MoneyValueVM, OperationTone
from app.web.ui.request_state import RequestStateVM

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
    def build_page(
        self,
        *,
        workspace_name: str,
        operations: Iterable[ManualOperationView],
        page: LedgerPage,
        filters: ManualOperationFilters,
        focused_operation_id: UUID | None,
        can_write: bool,
        references: ManualLedgerReferenceData | None = None,
        create_panel: ManualLedgerFormVM | None = None,
        reset_create_panel: bool = False,
        edit_panel: ManualLedgerEditPanelVM | None = None,
        reset_edit_panels: bool = False,
    ) -> ManualLedgerPageVM:
        filters_vm = self._filters(filters, page, references)
        page_state = ManualLedgerPageParams.from_list_state(
            filters=filters,
            page=page.page,
            per_page=page.per_page,
            focused_operation_id=focused_operation_id,
        )
        current_url = page_state.list_url()
        return ManualLedgerPageVM(
            workspace_name=workspace_name,
            total_label=self._total_label(page.total),
            readonly_message=self._readonly_message(can_write),
            create_region=self._create_region(
                can_write=can_write,
                current_url=current_url,
                panel=create_panel,
                reset_panel=reset_create_panel,
            ),
            rows=tuple(
                self.build_row(
                    operation,
                    focused_operation_id=focused_operation_id,
                    can_write=can_write,
                    return_to=current_url,
                    edit_panel=(
                        edit_panel
                        if edit_panel and edit_panel.operation_id == operation.id
                        else None
                    ),
                    reset_edit_panel=reset_edit_panels,
                )
                for operation in operations
            ),
            filters=filters_vm,
            show_pagination=page.total_pages > 1,
            page_label=f"Страница {page.page} из {page.total_pages}",
            previous_url=page_state.with_page(page.previous_page).list_url()
            if page.has_previous
            else None,
            next_url=page_state.with_page(page.next_page).list_url() if page.has_next else None,
            empty_title=(
                "По этим фильтрам операций нет" if filters_vm.active else "Ручных операций пока нет"
            ),
            empty_description=(
                "Измените условия поиска или сбросьте фильтры."
                if filters_vm.active
                else "Ручные операции появятся здесь после создания в рабочем интерфейсе."
            ),
        )

    def _create_region(
        self,
        *,
        can_write: bool,
        current_url: str,
        panel: ManualLedgerFormVM | None,
        reset_panel: bool,
    ) -> ManualLedgerCreateRegionVM | None:
        if not can_write:
            return None
        load_url = f"{MANUAL_LEDGER_URL}/new?{urlencode({'return_to': current_url})}"
        return ManualLedgerCreateRegionVM(
            action=DisclosureActionVM(
                label="Создать операцию",
                fallback_url=load_url,
                load_url=load_url,
                panel_id="manual-ledger-create-panel",
                load_target_id="manual-ledger-create-content",
                icon="plus",
            ),
            panel_id="manual-ledger-create-panel",
            content_id="manual-ledger-create-content",
            panel_open=panel is not None,
            reset_panel=reset_panel,
            panel=panel,
        )

    def build_row(
        self,
        operation: ManualOperationView,
        *,
        focused_operation_id: UUID | None,
        can_write: bool,
        return_to: str,
        edit_panel: ManualLedgerEditPanelVM | None = None,
        reset_edit_panel: bool = False,
        request_error: str | None = None,
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
            actions=ManualOperationActionPolicy().resolve(
                operation,
                can_write=can_write,
                return_to=return_to,
            ),
            request_state=RequestStateVM(
                phase="error" if request_error else "idle",
                message=request_error,
            ),
            is_targeted=focused_operation_id == operation.id,
            is_inactive=operation.status == OperationStatus.IGNORED,
            edit_panel_id=f"next-manual-operation-edit-panel-{operation.id}",
            edit_panel_content_id=f"next-manual-operation-edit-panel-content-{operation.id}",
            edit_panel_open=edit_panel is not None,
            reset_edit_panel=reset_edit_panel,
            edit_panel=edit_panel,
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

    def _filters(
        self,
        filters: ManualOperationFilters,
        page: LedgerPage,
        references: ManualLedgerReferenceData | None,
    ) -> ManualLedgerFiltersVM:
        reference_data = references or ManualLedgerReferenceData((), (), ())
        active = bool(
            filters.date_from
            or filters.date_to
            or filters.operation_type
            or filters.status
            or filters.account_id
            or filters.category_id
            or filters.property_id
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
            accounts=tuple(
                ManualLedgerFilterOptionVM(
                    value=str(account.id),
                    label=f"{account.name} · {account.currency}",
                    selected=filters.account_id == account.id,
                )
                for account in reference_data.accounts
            ),
            categories=tuple(
                ManualLedgerFilterOptionVM(
                    value=str(category.id),
                    label=category.name,
                    selected=filters.category_id == category.id,
                )
                for category in reference_data.categories
            ),
            properties=tuple(
                ManualLedgerFilterOptionVM(
                    value=str(property_.id),
                    label=property_.name,
                    selected=filters.property_id == property_.id,
                )
                for property_ in reference_data.properties
            ),
            per_page=page.per_page,
            per_page_options=PER_PAGE_OPTIONS,
            active=active,
            reset_url=MANUAL_LEDGER_URL,
        )

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
                "Операции можно создавать, исправлять, отменять и восстанавливать "
                "прямо в рабочем списке."
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
