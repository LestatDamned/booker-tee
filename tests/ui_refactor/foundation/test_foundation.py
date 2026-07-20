from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from app.web.templating import static_tree_version
from app.web.ui.actions import (
    ActionSetVM,
    DisclosureActionVM,
    LinkActionVM,
    SubmitActionVM,
)
from app.web.ui.money import MoneyFormatter


def test_replaced_frontend_next_foundation_is_removed(client: TestClient) -> None:
    response = client.get("/_next/foundation")

    assert response.status_code == 404


def test_money_formatter_keeps_financial_meaning_server_side() -> None:
    expense = MoneyFormatter.format(
        Decimal("-1234567.8"),
        "rub",
        operation_type="expense",
        entry_direction="outflow",
    )
    transfer = MoneyFormatter.format(
        Decimal("15000"),
        "RUB",
        operation_type="transfer",
        entry_direction="inflow",
    )

    assert expense.amount_label == "-1 234 567,80"
    assert expense.currency_label == "RUB"
    assert expense.modifier_classes == (
        "money-value--expense",
        "money-value--outflow",
    )
    assert transfer.amount_label == "15 000,00"
    assert transfer.operation_type == "transfer"
    assert transfer.entry_direction == "inflow"
    assert "money-value--income" not in transfer.modifier_classes


def test_action_set_uses_explicit_valid_action_types() -> None:
    actions = ActionSetVM(
        primary=DisclosureActionVM(
            label="Исправить",
            fallback_url="/operation/edit",
            load_url="/operation/edit/panel",
            panel_id="operation-edit-panel",
            load_target_id="operation-edit-panel-content",
            icon="edit",
        ),
        secondary=(LinkActionVM(label="Источник", url="/source", icon="source"),),
        danger=(
            SubmitActionVM(
                label="Удалить",
                url="/operation/delete",
                icon="trash",
                confirmation="Удалить операцию?",
            ),
        ),
    )

    assert actions.primary is not None
    assert actions.primary.kind == "disclosure"
    assert actions.secondary[0].kind == "link"
    assert actions.danger[0].kind == "submit"
    assert actions.danger[0].method == "post"


def test_static_tree_version_tracks_imported_asset_changes(tmp_path: Path) -> None:
    entry = tmp_path / "css" / "app.css"
    component = tmp_path / "css" / "components" / "workbench-row.css"
    component.parent.mkdir(parents=True)
    entry.write_text('@import url("./components/workbench-row.css");', encoding="utf-8")
    component.write_text(".workbench-row {}", encoding="utf-8")
    first_version = static_tree_version(tmp_path)

    component.write_text(".workbench-row { display: grid; }", encoding="utf-8")

    assert static_tree_version(tmp_path) != first_version
