from dataclasses import dataclass
from uuid import UUID

from app.features.imports.presentation.review.models import ActionSetVM, ActionVM
from app.features.imports.presentation.review.references import ReviewReferenceResolver


@dataclass(frozen=True)
class ReviewActionUrlBuilder:
    document_id: UUID

    def status_url(self, row_id: UUID) -> str:
        return f"/imports/documents/{self.document_id}/raw-transactions/{row_id}/status"

    def undo_posting_url(self, row_id: UUID) -> str:
        return f"/imports/documents/{self.document_id}/raw-transactions/{row_id}/undo-posting"

    def operation_url(self, operation_id: object) -> str:
        return f"/ledger/manual?operation_id={operation_id}"


class ReviewActionPolicy:
    def __init__(self, *, document_id: UUID) -> None:
        self.urls = ReviewActionUrlBuilder(document_id)

    def actions_for(
        self,
        row: object,
        *,
        visual_state: str,
        is_confirmable: bool,
        category_panel_id: str,
        transfer_panel_id: str,
        category_id: UUID | None,
        property_id: UUID | None,
    ) -> ActionSetVM:
        row_id = ReviewReferenceResolver.required_id(row)
        status_url = self.urls.status_url(row_id)
        undo_url = self.urls.undo_posting_url(row_id)

        if visual_state in {"confirmed", "matched"} and getattr(row, "linked_operation_id", None):
            return self._posted_actions(
                row,
                undo_url=undo_url,
            )

        if visual_state == "ignored":
            return ActionSetVM(
                primary=self._status_action(
                    status_url,
                    "needs_review",
                    "Восстановить",
                    "rotate-ccw",
                    "primary",
                ),
                visible_secondary=self._panel_action(
                    "details",
                    "Открыть детали",
                    category_panel_id,
                ),
                menu=[],
                danger=[],
            )

        if visual_state == "duplicate":
            return self._duplicate_actions(
                row,
                status_url=status_url,
                transfer_panel_id=transfer_panel_id,
            )

        if visual_state == "possible_duplicate":
            return ActionSetVM(
                primary=self._status_action(
                    status_url,
                    "mark_unique",
                    "Это новая операция",
                    "check",
                    "primary",
                ),
                visible_secondary=self._status_action(
                    status_url,
                    "needs_review",
                    "На проверку",
                    "clipboard-check",
                    "secondary",
                ),
                menu=[],
                danger=[
                    self._status_action(
                        status_url,
                        "ignore",
                        "Игнорировать",
                        "ignore",
                        "danger",
                        confirm_message="Игнорировать возможный дубль?",
                    )
                ],
            )

        if visual_state in {"suggested", "ready_to_confirm"} and is_confirmable:
            return self._confirmable_actions(
                status_url=status_url,
                visual_state=visual_state,
                category_panel_id=category_panel_id,
                transfer_panel_id=transfer_panel_id,
                category_id=category_id,
                property_id=property_id,
            )

        return ActionSetVM(
            primary=self._panel_action(
                "category_panel",
                "Разобрать",
                category_panel_id,
                placement="primary",
            ),
            visible_secondary=self._panel_action(
                "transfer_panel",
                "Сделать перевод",
                transfer_panel_id,
            ),
            menu=[
                self._status_action(
                    status_url,
                    "needs_review",
                    "На проверку",
                    "clipboard-check",
                    "secondary",
                )
            ],
            danger=[
                self._status_action(
                    status_url,
                    "ignore",
                    "Игнорировать",
                    "ignore",
                    "danger",
                    confirm_message="Игнорировать эту строку импорта?",
                )
            ],
        )

    def _posted_actions(
        self,
        row: object,
        *,
        undo_url: str,
    ) -> ActionSetVM:
        del row
        return ActionSetVM(
            primary=None,
            visible_secondary=None,
            menu=[],
            danger=[
                ActionVM(
                    id="undo_posting",
                    label="Отменить проведение",
                    icon="rotate-ccw",
                    placement="danger",
                    action_type="post",
                    url=undo_url,
                    style="danger",
                    confirm_message="Отменить связь строки с проведенной операцией?",
                )
            ],
        )

    def _duplicate_actions(
        self,
        row: object,
        *,
        status_url: str,
        transfer_panel_id: str,
    ) -> ActionSetVM:
        del transfer_panel_id
        primary = (
            ActionVM(
                id="open_operation",
                label="Открыть связанную операцию",
                icon="file-text",
                placement="primary",
                action_type="link",
                url=self.urls.operation_url(getattr(row, "linked_operation_id", "")),
            )
            if getattr(row, "linked_operation_id", None)
            else self._status_action(status_url, "mark_unique", "Это новая", "check", "primary")
        )
        return ActionSetVM(
            primary=primary,
            visible_secondary=self._status_action(
                status_url,
                "needs_review",
                "На проверку",
                "clipboard-check",
                "secondary",
            ),
            menu=[],
            danger=[
                self._status_action(
                    status_url,
                    "ignore",
                    "Игнорировать",
                    "ignore",
                    "danger",
                    confirm_message="Игнорировать эту строку импорта?",
                )
            ],
        )

    def _confirmable_actions(
        self,
        *,
        status_url: str,
        visual_state: str,
        category_panel_id: str,
        transfer_panel_id: str,
        category_id: UUID | None,
        property_id: UUID | None,
    ) -> ActionSetVM:
        hidden_fields: dict[str, str] = {"action": "confirm"}
        if category_id is not None:
            hidden_fields["category_id"] = str(category_id)
        if property_id is not None:
            hidden_fields["property_id"] = str(property_id)
        primary_label = "Подтвердить предложение" if visual_state == "suggested" else "Подтвердить"
        return ActionSetVM(
            primary=ActionVM(
                id="confirm",
                label=primary_label,
                icon="check",
                placement="primary",
                action_type="post",
                url=status_url,
                hidden_fields=hidden_fields,
            ),
            visible_secondary=self._panel_action(
                "category_panel",
                "Изменить",
                category_panel_id,
            ),
            menu=[
                self._panel_action("transfer_panel", "Сделать перевод", transfer_panel_id),
                self._status_action(
                    status_url,
                    "needs_review",
                    "На проверку",
                    "clipboard-check",
                    "secondary",
                ),
            ],
            danger=[
                self._status_action(
                    status_url,
                    "ignore",
                    "Игнорировать",
                    "ignore",
                    "danger",
                    confirm_message="Игнорировать эту строку импорта?",
                )
            ],
        )

    def _status_action(
        self,
        url: str,
        action: str,
        label: str,
        icon: str,
        placement: str,
        *,
        confirm_message: str | None = None,
    ) -> ActionVM:
        return ActionVM(
            id=action,
            label=label,
            icon=icon,
            placement=placement,
            action_type="post",
            url=url,
            hidden_fields={"action": action},
            style="danger" if placement == "danger" else "default",
            confirm_message=confirm_message,
        )

    def _panel_action(
        self,
        action_id: str,
        label: str,
        panel_id: str,
        *,
        placement: str = "secondary",
    ) -> ActionVM:
        return ActionVM(
            id=action_id,
            label=label,
            icon="settings" if action_id == "category_panel" else "refresh",
            placement=placement,
            action_type="panel_toggle",
            panel_id=panel_id,
        )
