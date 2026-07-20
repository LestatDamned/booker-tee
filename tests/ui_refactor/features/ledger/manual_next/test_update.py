from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from manual_ledger_support import (
    manual_expense,
    manual_ledger_app,
    valid_edit_form,
    workspace_context,
)

from app.features.ledger.application.listing import (
    LedgerPage,
    LedgerPagination,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.workspaces.models import WorkspaceRole
from app.web.features.ledger.manual.forms import (
    ManualLedgerEditValidation,
    ManualLedgerFormInput,
)
from app.web.features.ledger.manual.query_state import (
    MANUAL_LEDGER_URL,
    safe_manual_ledger_return_to,
)


def test_edit_panel_loads_lazily_and_http_fallback_opens_full_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.page = LedgerPage(page=1, per_page=50, total=1)
    edit_url = f"/_next/ledger/manual/{operation.id}/edit"

    with TestClient(app) as client:
        page_response = client.get("/_next/ledger/manual")
        panel_response = client.get(edit_url, headers={"HX-Request": "true"})
        fallback = client.get(edit_url, follow_redirects=False)

    assert page_response.status_code == 200
    assert f'id="next-manual-operation-form-{operation.id}"' not in page_response.text
    assert f'hx-get="{edit_url}?' in page_response.text
    assert (
        f'hx-target="#next-manual-operation-edit-panel-content-{operation.id}"'
        in page_response.text
    )
    assert f'id="next-manual-operation-edit-panel-content-{operation.id}"' in page_response.text
    assert panel_response.status_code == 200
    assert f'id="next-manual-operation-form-{operation.id}"' in panel_response.text
    assert 'name="version" value="1"' in panel_response.text
    assert f'hx-post="{MANUAL_LEDGER_URL}/{operation.id}"' in panel_response.text
    assert "<html" not in panel_response.text
    assert fallback.status_code == 200
    assert "<!doctype html>" in fallback.text
    assert "Исправить операцию" in fallback.text
    assert f'id="next-manual-operation-form-{operation.id}"' in fallback.text
    assert f'hx-post="/_next/ledger/manual/{operation.id}"' not in fallback.text
    assert 'x-on:click.prevent="cancel()"' not in fallback.text


def test_htmx_validation_returns_open_row_and_preserves_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.page = LedgerPage(page=1, per_page=50, total=1)
    form = valid_edit_form(operation)
    form["amount"] = "0"
    form["description"] = "Черновик пользователя"

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{operation.id}",
            data=form,
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 422
    assert "<html" not in response.text
    assert f'id="next-operation-{operation.id}"' in response.text
    assert 'x-data="disclosure(true)"' in response.text
    assert 'value="Черновик пользователя"' in response.text
    assert 'value="0"' in response.text
    assert "Сумма должна быть больше нуля" in response.text
    assert 'aria-invalid="true"' in response.text
    assert calls.update_commands == []


def test_http_validation_returns_full_page_with_preserved_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.page = LedgerPage(page=1, per_page=50, total=1)
    form = valid_edit_form(operation)
    form["operation_date"] = "bad-date"

    with TestClient(app) as client:
        response = client.post(f"/_next/ledger/manual/{operation.id}", data=form)

    assert response.status_code == 422
    assert "<!doctype html>" in response.text
    assert "Исправить операцию" in response.text
    assert f'id="next-manual-operation-form-{operation.id}"' in response.text
    assert 'value="bad-date"' in response.text
    assert "Выберите корректную дату" in response.text
    assert 'id="manual-ledger-results"' not in response.text


def test_successful_update_has_htmx_replace_row_and_http_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.page = LedgerPage(page=1, per_page=50, total=1)
    form = valid_edit_form(operation)
    form["description"] = "Обновлённое описание"

    with TestClient(app) as client:
        htmx = client.post(
            f"/_next/ledger/manual/{operation.id}",
            data=form,
            headers={"HX-Request": "true"},
        )
        form["version"] = "2"
        fallback = client.post(
            f"/_next/ledger/manual/{operation.id}",
            data=form,
            follow_redirects=False,
        )

    assert htmx.status_code == 200
    assert "<html" not in htmx.text
    assert f'id="next-operation-{operation.id}"' in htmx.text
    assert "Обновлённое описание" in htmx.text
    assert f'id="next-manual-operation-form-{operation.id}"' not in htmx.text
    assert "data-disclosure-reset" in htmx.text
    assert fallback.status_code == 303
    assert fallback.headers["location"].startswith("/_next/ledger/manual?")
    assert fallback.headers["location"].endswith(f"#next-operation-{operation.id}")
    assert len(calls.update_commands) == 2
    assert [command.expected_version for command in calls.update_commands] == [1, 2]
    assert set(calls.updated_workspace_ids) == {context.workspace.id}


def test_update_with_active_filter_conservatively_replaces_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.realistic_listing = True
    form = valid_edit_form(operation)
    form["description"] = "Расход остался расходом"
    form["return_to"] = f"{MANUAL_LEDGER_URL}?type=expense&page=1&per_page=50"

    with TestClient(app) as client:
        response = client.post(
            f"{MANUAL_LEDGER_URL}/{operation.id}",
            data=form,
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#manual-ledger-results"
    assert f'id="next-operation-{operation.id}"' in response.text
    assert "Расход остался расходом" in response.text


def test_stale_update_returns_local_409_and_preserves_user_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    loaded_operation = manual_expense()
    calls.operations = [
        replace(
            loaded_operation,
            version=2,
            description="Изменено в другом окне",
        )
    ]
    form = valid_edit_form(loaded_operation)
    form["description"] = "Мой несохранённый вариант"

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{loaded_operation.id}",
            data=form,
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 409
    assert "Операция уже изменилась в другом окне" in response.text
    assert 'value="Мой несохранённый вариант"' in response.text
    assert 'name="version" value="1"' in response.text
    assert "Загрузить актуальную версию" in response.text
    assert (
        f'hx-target="#next-manual-operation-edit-panel-content-{loaded_operation.id}"'
        in response.text
    )
    assert calls.operations[0].description == "Изменено в другом окне"
    assert calls.refreshed_workspace_ids == [context.workspace.id]


def test_missing_edit_version_returns_local_422_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    form = valid_edit_form(operation)
    form["version"] = ""

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{operation.id}",
            data=form,
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 422
    assert "Версия формы устарела или повреждена" in response.text
    assert calls.update_commands == []


def test_stale_update_http_fallback_returns_full_409_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    loaded_operation = manual_expense()
    calls.operations = [replace(loaded_operation, version=2)]
    form = valid_edit_form(loaded_operation)
    form["description"] = "Черновик обычного HTTP-запроса"

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{loaded_operation.id}",
            data=form,
        )

    assert response.status_code == 409
    assert "<!doctype html>" in response.text
    assert 'value="Черновик обычного HTTP-запроса"' in response.text
    assert "Загрузить актуальную версию" in response.text
    assert "hx-get=" not in response.text


def test_update_that_leaves_filter_replaces_results_and_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.realistic_listing = True
    form = valid_edit_form(operation)
    form["operation_type"] = "income"
    form["return_to"] = "/_next/ledger/manual?type=expense&page=1&per_page=50"

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{operation.id}",
            data=form,
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#manual-ledger-results"
    assert response.headers["HX-Reswap"] == "outerHTML"
    assert response.headers["HX-Replace-Url"].startswith("/_next/ledger/manual?page=1&per_page=50")
    assert '<div\n  id="manual-ledger-results"' in response.text
    assert f'id="next-operation-{operation.id}"' not in response.text
    assert 'id="manual-ledger-total"' in response.text
    assert 'hx-swap-oob="outerHTML"' in response.text
    assert "0 ручных операций" in response.text
    assert "По этим фильтрам операций нет" in response.text


def test_update_that_leaves_category_filter_replaces_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    category_id = uuid4()
    operation = replace(manual_expense(), category_id=category_id)
    calls.operations = [operation]
    calls.realistic_listing = True
    form = valid_edit_form(operation)
    form["category_id"] = ""
    form["return_to"] = f"/_next/ledger/manual?category_id={category_id}&page=1&per_page=50"

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{operation.id}",
            data=form,
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#manual-ledger-results"
    assert f'id="next-operation-{operation.id}"' not in response.text
    assert "0 ручных операций" in response.text


def test_date_change_replaces_sorted_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    other = replace(
        manual_expense(),
        operation_date=date(2026, 7, 10),
        description="Другая операция",
    )
    calls.operations = [operation, other]
    calls.realistic_listing = True
    form = valid_edit_form(operation)
    form["operation_date"] = "2026-07-01"

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{operation.id}",
            data=form,
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#manual-ledger-results"
    assert "data-disclosure-reset" in response.text
    assert "350,00" in response.text
    assert response.text.index(f'id="next-operation-{other.id}"') < response.text.index(
        f'id="next-operation-{operation.id}"'
    )


def test_replace_list_normalizes_a_page_that_no_longer_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.realistic_listing = True
    form = valid_edit_form(operation)
    form["operation_type"] = "income"
    form["return_to"] = "/_next/ledger/manual?type=expense&page=2&per_page=1"

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{operation.id}",
            data=form,
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 200
    assert calls.paginations[-2:] == [
        LedgerPagination(page=2, per_page=1),
        LedgerPagination(page=1, per_page=1),
    ]
    assert response.headers["HX-Replace-Url"].startswith("/_next/ledger/manual?page=1&per_page=1")
    assert "Страница 2 из 1" not in response.text


def test_business_error_returns_localized_422_row(monkeypatch: pytest.MonkeyPatch) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.page = LedgerPage(page=1, per_page=50, total=1)
    calls.update_error = LedgerPostingError("Account is not available in this workspace.")

    with TestClient(app) as client:
        response = client.post(
            f"/_next/ledger/manual/{operation.id}",
            data=valid_edit_form(operation),
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 422
    assert "Выбранный счёт недоступен в этом workspace" in response.text
    assert 'role="alert"' in response.text
    assert calls.refreshed_workspace_ids == [context.workspace.id]


def test_edit_requires_financial_write_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    context = workspace_context(role=WorkspaceRole.VIEWER)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]

    with TestClient(app) as client:
        response = client.get(
            f"/_next/ledger/manual/{operation.id}/edit",
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 403


def test_edit_validation_rejects_same_transfer_accounts() -> None:
    account_id = uuid4()
    validation = ManualLedgerEditValidation.from_form_input(
        operation_id=uuid4(),
        form_input=ManualLedgerFormInput(
            version="1",
            operation_type="transfer",
            account_id=str(account_id),
            destination_account_id=str(account_id),
            amount="100,50",
            operation_date="2026-07-17",
        ),
    )

    assert validation.command is None
    assert [(issue.field, issue.message) for issue in validation.issues] == [
        ("destination_account_id", "Счета перевода должны отличаться."),
    ]


def test_edit_return_url_cannot_leave_manual_ledger() -> None:
    assert safe_manual_ledger_return_to("https://example.com/steal") == MANUAL_LEDGER_URL
    assert safe_manual_ledger_return_to("//example.com/steal") == MANUAL_LEDGER_URL
    assert (
        safe_manual_ledger_return_to("/_next/ledger/manual?page=2&search=кофе")
        == "/_next/ledger/manual?page=2&search=кофе"
    )
