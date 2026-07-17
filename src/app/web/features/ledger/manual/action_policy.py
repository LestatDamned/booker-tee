from urllib.parse import urlencode

from app.features.ledger.mapping.dto import ManualOperationView
from app.features.ledger.models import OperationStatus
from app.web.features.ledger.manual.query_state import MANUAL_LEDGER_URL
from app.web.ui.actions import (
    ActionSetVM,
    DisclosureActionVM,
    LinkActionVM,
    SubmitActionVM,
)


class ManualOperationActionPolicy:
    def resolve(
        self,
        operation: ManualOperationView,
        *,
        can_write: bool,
        return_to: str,
    ) -> ActionSetVM:
        if not can_write:
            return self._legacy_action(operation)
        if operation.status == OperationStatus.CONFIRMED:
            return ActionSetVM(
                primary=self._edit(operation, return_to),
                danger=(
                    self._submit(
                        operation,
                        action="cancel",
                        label="Отменить операцию",
                        icon="archive",
                        confirmation=(
                            "Отменить операцию? Она перестанет влиять на баланс и отчёты."
                        ),
                        return_to=return_to,
                    ),
                ),
            )
        if operation.status == OperationStatus.IGNORED:
            return ActionSetVM(
                primary=self._submit(
                    operation,
                    action="restore",
                    label="Восстановить",
                    icon="rotate-ccw",
                    confirmation=(
                        "Восстановить операцию? Она снова будет влиять на баланс и отчёты."
                    ),
                    return_to=return_to,
                ),
                danger=(self._delete(operation, return_to),),
            )
        if operation.status == OperationStatus.DRAFT:
            return ActionSetVM(
                primary=self._edit(operation, return_to),
                danger=(self._delete(operation, return_to),),
            )
        return self._legacy_action(operation)

    def _edit(
        self,
        operation: ManualOperationView,
        return_to: str,
    ) -> DisclosureActionVM:
        edit_url = f"{MANUAL_LEDGER_URL}/{operation.id}/edit?{urlencode({'return_to': return_to})}"
        return DisclosureActionVM(
            label="Исправить",
            fallback_url=edit_url,
            load_url=edit_url,
            panel_id=f"next-manual-operation-edit-panel-{operation.id}",
            load_target_id=f"next-manual-operation-edit-panel-content-{operation.id}",
            icon="edit",
        )

    def _delete(
        self,
        operation: ManualOperationView,
        return_to: str,
    ) -> SubmitActionVM:
        return self._submit(
            operation,
            action="delete",
            label="Удалить окончательно",
            icon="trash",
            confirmation=(
                "Удалить операцию без возможности восстановления? Финансовая запись исчезнет."
            ),
            return_to=return_to,
        )

    def _submit(
        self,
        operation: ManualOperationView,
        *,
        action: str,
        label: str,
        icon: str,
        confirmation: str,
        return_to: str,
    ) -> SubmitActionVM:
        return SubmitActionVM(
            label=label,
            url=f"{MANUAL_LEDGER_URL}/{operation.id}/{action}",
            icon=icon,
            confirmation=confirmation,
            hidden_fields={"return_to": return_to},
            target_id=f"next-operation-{operation.id}",
        )

    def _legacy_action(self, operation: ManualOperationView) -> ActionSetVM:
        return ActionSetVM(
            secondary=(
                LinkActionVM(
                    label="Открыть текущую версию",
                    url=(f"/ledger/manual?operation_id={operation.id}#operation-{operation.id}"),
                    icon="source",
                ),
            )
        )
