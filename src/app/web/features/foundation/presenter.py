from decimal import Decimal

from app.web.features.foundation.view_models import FoundationPreviewVM
from app.web.ui.actions import (
    ActionSetVM,
    DisclosureActionVM,
    LinkActionVM,
    SubmitActionVM,
)
from app.web.ui.money import MoneyFormatter
from app.web.ui.request_state import FieldErrorVM, RequestStateVM


class FoundationPreviewPresenter:
    @staticmethod
    def present(*, edit_panel_open: bool = False) -> FoundationPreviewVM:
        return FoundationPreviewVM(
            expense=MoneyFormatter.format(
                Decimal("-744.94"),
                "RUB",
                operation_type="expense",
                entry_direction="outflow",
            ),
            transfer=MoneyFormatter.format(
                Decimal("15000"),
                "RUB",
                operation_type="transfer",
                entry_direction="inflow",
            ),
            actions=ActionSetVM(
                primary=DisclosureActionVM(
                    label="Исправить",
                    fallback_url="/_next/foundation?edit=1",
                    load_url="/_next/foundation/panel",
                    panel_id="foundation-edit-panel",
                    load_target_id="foundation-edit-panel-content",
                    icon="edit",
                ),
                secondary=(
                    LinkActionVM(
                        label="Открыть источник",
                        url="/_next/foundation",
                        icon="source",
                    ),
                ),
                menu=(
                    SubmitActionVM(
                        label="Повторить",
                        url="/_next/foundation",
                        icon="retry",
                        disabled=True,
                        disabled_reason="Витрина не отправляет mutation-запросы.",
                    ),
                ),
                danger=(
                    SubmitActionVM(
                        label="Удалить",
                        url="/_next/foundation",
                        icon="trash",
                        confirmation="Удалить пример?",
                        disabled=True,
                        disabled_reason="Витрина не изменяет данные.",
                    ),
                ),
            ),
            request_state=RequestStateVM(),
            request_error=RequestStateVM(
                phase="error",
                message="Не удалось обновить строку. Данные на странице сохранены.",
                retry_action=LinkActionVM(
                    label="Повторить",
                    url="/_next/foundation",
                    icon="retry",
                ),
            ),
            field_error=FieldErrorVM(
                field_id="foundation-description",
                error_id="foundation-description-error",
                message="Добавьте понятное описание.",
            ),
            edit_panel_open=edit_panel_open,
        )
