from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from manual_ledger_support import (
    manual_expense,
    manual_ledger_app,
    manual_transfer,
    workspace_context,
)

from app.features.ledger.application.listing import (
    LedgerPage,
    LedgerPagination,
    ManualOperationFilters,
)
from app.features.ledger.models import OperationStatus, OperationType
from app.features.workspaces.models import WorkspaceMemberStatus, WorkspaceRole
from app.web.features.ledger.manual.presenter import ManualLedgerPresenter
from app.web.features.ledger.manual.query_state import (
    MANUAL_LEDGER_URL,
    ManualLedgerPageParams,
    ManualLedgerUrlState,
)
from app.web.ui.actions import DisclosureActionVM, SubmitActionVM


def test_page_params_build_from_url_state_and_return_url() -> None:
    focused_operation_id = uuid4()
    url_state = ManualLedgerUrlState(
        date_from=date(2026, 7, 1),
        type=OperationType.EXPENSE,
        status=OperationStatus.CONFIRMED,
        search="  магазин  ",
        operation_id=focused_operation_id,
        page=2,
        per_page=25,
    )

    from_state = ManualLedgerPageParams.from_url_state(url_state)
    return_to_state = ManualLedgerUrlState.from_return_to(
        f"{MANUAL_LEDGER_URL}?date_from=2026-07-01&type=expense&status=confirmed"
        f"&search=++магазин++&operation_id={focused_operation_id}&page=2&per_page=25"
    )
    from_return_to = ManualLedgerPageParams.from_url_state(return_to_state)

    assert from_state == from_return_to
    assert from_state.filters.date_from == date(2026, 7, 1)
    assert from_state.filters.operation_type is OperationType.EXPENSE
    assert from_state.filters.status is OperationStatus.CONFIRMED
    assert from_state.filters.search == "магазин"
    assert from_state.pagination == LedgerPagination(page=2, per_page=25)
    assert return_to_state.focused_operation_id == focused_operation_id


def test_url_state_tolerantly_normalizes_untrusted_query_values() -> None:
    operation_id = uuid4()

    state = ManualLedgerUrlState.from_return_to(
        f"{MANUAL_LEDGER_URL}?date_from=wrong&date_to=2026-06-01&type=wrong"
        f"&status=confirmed&operation_id={uuid4()}&operation_id={operation_id}"
        "&account_id=wrong&search=++Кофе++с++молоком++&page=-3&per_page=999"
        "&unknown=value"
    )

    assert state.date_from is None
    assert state.date_to == date(2026, 6, 1)
    assert state.operation_type_filter is None
    assert state.status_filter is OperationStatus.CONFIRMED
    assert state.account_id is None
    assert state.search == "Кофе  с  молоком"
    assert state.operation_id == operation_id
    assert state.page == 1
    assert state.per_page == 200


def test_url_state_owns_canonical_list_and_target_urls() -> None:
    focused_operation_id = uuid4()
    state = ManualLedgerUrlState(
        type=OperationType.EXPENSE,
        operation_id=focused_operation_id,
        page=1,
        per_page=50,
    )

    assert state.list_url().startswith(f"{MANUAL_LEDGER_URL}?page=1&per_page=50")
    assert f"operation_id={focused_operation_id}" in state.list_url()

    target_operation_id = uuid4()
    target_url = state.target_operation_url(target_operation_id)
    assert f"operation_id={target_operation_id}" in target_url
    assert target_url.endswith(f"#next-operation-{target_operation_id}")

    settled_url = ManualLedgerUrlState.from_return_to(target_url).clear_operation_target_url()
    assert "operation_id=" not in settled_url


def test_presenter_builds_server_owned_financial_and_action_contracts() -> None:
    operation = manual_expense()

    page = ManualLedgerPresenter().build_page(
        workspace_name="Дом",
        operations=[operation],
        pagination=LedgerPage(page=1, per_page=50, total=1),
        filters=ManualOperationFilters(),
        focused_operation_id=operation.id,
        can_write=True,
    )

    row = page.rows[0]
    assert row.id == f"next-operation-{operation.id}"
    assert row.money is not None
    assert row.money.amount_label == "350,00"
    assert row.money.operation_type == "expense"
    assert row.money.entry_direction == "outflow"
    assert row.status_label == "подтверждено"
    assert row.is_targeted is True
    assert isinstance(row.actions.primary, DisclosureActionVM)
    assert row.actions.primary.load_url.startswith(f"/_next/ledger/manual/{operation.id}/edit")
    assert len(row.actions.danger) == 1
    cancel_action = row.actions.danger[0]
    assert isinstance(cancel_action, SubmitActionVM)
    assert cancel_action.url == f"/_next/ledger/manual/{operation.id}/cancel"
    assert cancel_action.target_id == row.id
    assert page.filters.active is False
    assert page.total_label == "1 ручная операция"


def test_presenter_exposes_restore_and_delete_only_for_cancelled_operation() -> None:
    operation = replace(manual_expense(), status=OperationStatus.IGNORED)

    row = ManualLedgerPresenter().build_row(
        operation,
        focused_operation_id=None,
        can_write=True,
        return_to=MANUAL_LEDGER_URL,
    )

    assert isinstance(row.actions.primary, SubmitActionVM)
    assert row.actions.primary.url.endswith(f"/{operation.id}/restore")
    assert len(row.actions.danger) == 1
    delete_action = row.actions.danger[0]
    assert isinstance(delete_action, SubmitActionVM)
    assert delete_action.url.endswith(f"/{operation.id}/delete")


def test_presenter_keeps_transfer_separate_from_profit() -> None:
    operation = manual_transfer()

    page = ManualLedgerPresenter().build_page(
        workspace_name="Дом",
        operations=[operation],
        pagination=LedgerPage(page=1, per_page=50, total=1),
        filters=ManualOperationFilters(),
        focused_operation_id=None,
        can_write=False,
    )

    row = page.rows[0]
    assert row.money is not None
    assert row.money.operation_type == "transfer"
    assert row.money.entry_direction is None
    assert row.operation_tone == "transfer"
    assert [meta.label for meta in row.meta] == ["Карта → Наличные"]
    assert row.actions.primary is None
    assert row.actions.secondary


def test_readonly_route_lists_real_workspace_data_and_preserves_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.page = LedgerPage(page=2, per_page=25, total=30)

    with TestClient(app) as client:
        response = client.get(
            f"/_next/ledger/manual?type=expense&status=confirmed&search=coffee"
            f"&operation_id={operation.id}&page=2&per_page=25"
        )

    assert response.status_code == 200
    assert "Операции можно создавать, исправлять, отменять" in response.text
    assert f'id="next-operation-{operation.id}"' in response.text
    assert "workbench-row--target" in response.text
    assert "money-value--expense" in response.text
    assert '<body hx-history="false">' in response.text
    assert "src/app/static/css/app.css" not in response.text
    assert "financial-row" not in response.text
    assert 'option value="expense" selected' in response.text
    assert set(calls.workspace_ids) == {context.workspace.id}
    assert calls.filters[0].operation_type is OperationType.EXPENSE
    assert calls.filters[0].status is OperationStatus.CONFIRMED
    assert calls.filters[0].search == "coffee"
    assert calls.paginations == [LedgerPagination(page=2, per_page=25)]


def test_route_ignores_invalid_known_and_unknown_query_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)

    with TestClient(app) as client:
        response = client.get(
            f"{MANUAL_LEDGER_URL}?date_from=wrong&type=wrong&account_id=wrong"
            "&page=wrong&per_page=wrong&unknown=value"
        )

    assert response.status_code == 200
    assert calls.filters[0].date_from is None
    assert calls.filters[0].operation_type is None
    assert calls.filters[0].account_id is None
    assert calls.paginations == [LedgerPagination(page=1, per_page=50)]


def test_route_is_readable_for_viewer_but_hides_write_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.VIEWER)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    calls.operations = [manual_expense()]

    with TestClient(app) as client:
        response = client.get("/_next/ledger/manual")

    assert response.status_code == 200
    assert "согласно вашей роли" in response.text
    assert "Изменить в текущем интерфейсе" not in response.text
    assert "Открыть текущую версию" in response.text


def test_route_applies_and_preserves_workspace_reference_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    primary_entry = operation.primary_entry
    assert primary_entry is not None
    category = SimpleNamespace(id=uuid4(), name="Продукты")
    property_ = SimpleNamespace(id=uuid4(), name="Красное Белое")
    calls.operations = [
        replace(
            operation,
            category_id=category.id,
            property_id=property_.id,
        )
    ]
    calls.categories = [category]
    calls.properties = [property_]
    calls.page = LedgerPage(page=1, per_page=25, total=30)

    with TestClient(app) as client:
        response = client.get(
            "/_next/ledger/manual",
            params={
                "account_id": str(primary_entry.account_id),
                "category_id": str(category.id),
                "property_id": str(property_.id),
                "per_page": "25",
            },
        )

    assert response.status_code == 200
    assert f'<option value="{primary_entry.account_id}" selected>' in response.text
    assert f'<option value="{category.id}" selected>Продукты</option>' in response.text
    assert f'<option value="{property_.id}" selected>Красное Белое</option>' in response.text
    filters = calls.filters[0]
    assert filters.account_id == primary_entry.account_id
    assert filters.category_id == category.id
    assert filters.property_id == property_.id
    assert f"account_id={primary_entry.account_id}" in response.text
    assert f"category_id={category.id}" in response.text
    assert f"property_id={property_.id}" in response.text


def test_transfer_row_uses_financial_badge_and_correct_text_hierarchy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_transfer()
    calls.operations = [operation]
    calls.page = LedgerPage(page=1, per_page=50, total=1)

    with TestClient(app) as client:
        response = client.get("/_next/ledger/manual")

    assert response.status_code == 200
    assert '<p class="workbench-row__title">17.07.2026</p>' in response.text
    assert '<p class="workbench-row__description">Снятие наличных</p>' in response.text
    assert "ui-badge--transfer" in response.text
    assert "не влияет на прибыль" not in response.text


def test_route_rejects_inactive_workspace_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(
        role=WorkspaceRole.VIEWER,
        status=WorkspaceMemberStatus.DISABLED,
    )
    app, _calls = manual_ledger_app(monkeypatch, context=context)

    with TestClient(app) as client:
        response = client.get("/_next/ledger/manual")

    assert response.status_code == 403


def test_empty_filtered_page_gives_recovery_action(monkeypatch: pytest.MonkeyPatch) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, _calls = manual_ledger_app(monkeypatch, context=context)

    with TestClient(app) as client:
        response = client.get("/_next/ledger/manual?search=missing")

    assert response.status_code == 200
    assert "По этим фильтрам операций нет" in response.text
    assert "Сбросить фильтры" in response.text
