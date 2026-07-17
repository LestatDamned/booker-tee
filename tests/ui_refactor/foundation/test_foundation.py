from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.web.features.foundation.presenter import FoundationPreviewPresenter
from app.web.features.foundation.routes import require_non_production
from app.web.templating import static_tree_version
from app.web.ui.actions import (
    ActionSetVM,
    DisclosureActionVM,
    LinkActionVM,
    SubmitActionVM,
)
from app.web.ui.money import MoneyFormatter


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


def test_foundation_preview_uses_isolated_templates_and_assets(client: TestClient) -> None:
    response = client.get("/_next/foundation")

    assert response.status_code == 200
    assert 'data-theme="catppuccin-mocha"' in response.text
    assert 'href="http://testserver/_next/static/css/app.css?' in response.text
    assert 'href="http://testserver/static/css/app.css' not in response.text
    assert 'src="http://testserver/_next/static/js/web-ui.js?' in response.text
    assert "financial-row" not in response.text
    assert "entity-card--working" not in response.text
    assert "workbench-row" in response.text
    assert "money-value--transfer" in response.text
    assert 'role="alert"' in response.text
    assert 'aria-describedby="foundation-description-error"' in response.text
    assert "ID операции" not in response.text
    assert 'class="workbench-row workbench-row--working"' not in response.text


def test_foundation_panel_is_a_local_htmx_fragment(client: TestClient) -> None:
    response = client.get("/_next/foundation/panel", headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert "data-edit-panel" in response.text
    assert "<html" not in response.text


def test_foundation_preview_is_not_available_in_production() -> None:
    with pytest.raises(HTTPException) as error:
        require_non_production(Settings(environment="production"))

    assert error.value.status_code == 404


def test_disclosure_fallback_renders_open_panel_without_htmx(client: TestClient) -> None:
    response = client.get("/_next/foundation?edit=true")

    assert response.status_code == 200
    assert 'x-data="disclosure(true)"' in response.text
    assert "data-edit-panel" in response.text


def test_foundation_presenter_returns_immutable_component_contracts() -> None:
    preview = FoundationPreviewPresenter.present()

    assert preview.expense.operation_type == "expense"
    assert preview.transfer.operation_type == "transfer"
    assert preview.actions.primary is not None
    assert preview.request_state.phase == "idle"
    assert preview.request_error.has_error is True
    assert preview.field_error.field_id == "foundation-description"
    assert preview.edit_panel_open is False


def test_static_tree_version_tracks_imported_asset_changes(tmp_path: Path) -> None:
    entry = tmp_path / "css" / "app.css"
    component = tmp_path / "css" / "components" / "workbench-row.css"
    component.parent.mkdir(parents=True)
    entry.write_text('@import url("./components/workbench-row.css");', encoding="utf-8")
    component.write_text(".workbench-row {}", encoding="utf-8")
    first_version = static_tree_version(tmp_path)

    component.write_text(".workbench-row { display: grid; }", encoding="utf-8")

    assert static_tree_version(tmp_path) != first_version
