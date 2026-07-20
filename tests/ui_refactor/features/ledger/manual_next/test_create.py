from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from manual_ledger_support import (
    manual_expense,
    manual_ledger_app,
    manual_transfer,
    valid_edit_form,
    workspace_context,
)

from app.features.ledger.application.commands import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
)
from app.features.ledger.application.listing import (
    LedgerPage,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.workspaces.models import WorkspaceRole
from app.web.features.ledger.manual.forms import (
    ManualLedgerCreateValidation,
    ManualLedgerFormInput,
)
from app.web.features.ledger.manual.query_state import (
    MANUAL_LEDGER_URL,
)


def test_create_validation_builds_income_and_transfer_commands() -> None:
    source_id = uuid4()
    destination_id = uuid4()
    income = ManualLedgerCreateValidation.from_form_input(
        form_input=ManualLedgerFormInput(
            operation_type="income",
            account_id=str(source_id),
            amount="1250,50",
            operation_date="2026-07-17",
            description="Проценты",
        )
    )
    transfer = ManualLedgerCreateValidation.from_form_input(
        form_input=ManualLedgerFormInput(
            operation_type="transfer",
            account_id=str(source_id),
            destination_account_id=str(destination_id),
            amount="5000",
            operation_date="2026-07-17",
            description="Перевод между счетами",
        )
    )

    assert isinstance(income.command, CreateManualIncomeExpenseCommand)
    assert income.command.amount == Decimal("1250.50")
    assert isinstance(transfer.command, CreateManualTransferCommand)
    assert transfer.command.source_account_id == source_id
    assert transfer.command.destination_account_id == destination_id


@pytest.mark.parametrize(
    ("overrides", "expected_issue"),
    [
        (
            {"operation_type": "unknown"},
            ("operation_type", "Выберите тип операции."),
        ),
        (
            {"account_id": ""},
            ("account_id", "Выберите счёт."),
        ),
        (
            {"account_id": "not-a-uuid"},
            ("account_id", "Выберите допустимое значение."),
        ),
        (
            {"amount": "not-money"},
            ("amount", "Введите корректную сумму."),
        ),
        (
            {"operation_date": "not-a-date"},
            ("operation_date", "Выберите корректную дату."),
        ),
        (
            {"category_id": "not-a-uuid"},
            ("category_id", "Выберите допустимое значение."),
        ),
        (
            {"operation_type": "transfer", "destination_account_id": ""},
            ("destination_account_id", "Выберите счёт назначения."),
        ),
    ],
)
def test_pydantic_form_validation_returns_localized_field_issues(
    overrides: dict[str, str],
    expected_issue: tuple[str, str],
) -> None:
    values = {
        "operation_type": "income",
        "account_id": str(uuid4()),
        "amount": "1250,50",
        "operation_date": "2026-07-17",
        **overrides,
    }

    validation = ManualLedgerCreateValidation.from_form_input(
        form_input=ManualLedgerFormInput(**values)
    )

    assert validation.command is None
    assert [(issue.field, issue.message) for issue in validation.issues] == [expected_issue]


def test_create_panel_loads_lazily_and_has_http_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    calls.operations = [manual_expense()]
    calls.page = LedgerPage(page=1, per_page=50, total=1)

    with TestClient(app) as client:
        page_response = client.get(MANUAL_LEDGER_URL)
        panel_response = client.get(
            f"{MANUAL_LEDGER_URL}/new",
            headers={"HX-Request": "true"},
        )
        fallback = client.get(f"{MANUAL_LEDGER_URL}/new", follow_redirects=False)

    assert page_response.status_code == 200
    assert 'id="next-manual-operation-create-form"' not in page_response.text
    assert 'hx-get="/_next/ledger/manual/new?' in page_response.text
    assert panel_response.status_code == 200
    assert 'id="next-manual-operation-create-form"' in panel_response.text
    assert 'value="income"' in panel_response.text
    assert fallback.status_code == 200
    assert "<!doctype html>" in fallback.text
    assert "Добавить ручную операцию" in fallback.text
    assert 'id="next-manual-operation-create-form"' in fallback.text
    assert 'hx-post="/_next/ledger/manual/new"' not in fallback.text
    assert 'x-on:click.prevent="cancel()"' not in fallback.text


def test_create_validation_returns_local_422_and_preserves_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    form = valid_edit_form(operation)
    form["amount"] = "0"
    form["description"] = "Новая операция"

    with TestClient(app) as client:
        response = client.post(
            f"{MANUAL_LEDGER_URL}/new",
            data=form,
            headers={"HX-Request": "true"},
        )
        fallback = client.post(f"{MANUAL_LEDGER_URL}/new", data=form)

    assert response.status_code == 422
    assert "Сумма должна быть больше нуля" in response.text
    assert 'value="Новая операция"' in response.text
    assert calls.income_expense_commands == []
    assert calls.transfer_commands == []
    assert fallback.status_code == 422
    assert "<!doctype html>" in fallback.text
    assert "Добавить ручную операцию" in fallback.text
    assert 'id="next-manual-operation-create-form"' in fallback.text
    assert 'id="manual-ledger-results"' not in fallback.text


def test_create_business_error_refreshes_workspace_before_rendering_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.update_error = LedgerPostingError("Account is not available in this workspace.")

    with TestClient(app) as client:
        response = client.post(
            f"{MANUAL_LEDGER_URL}/new",
            data=valid_edit_form(operation),
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 422
    assert "Выбранный счёт недоступен в этом workspace" in response.text
    assert calls.refreshed_workspace_ids == [context.workspace.id]


def test_successful_create_replaces_list_total_and_create_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.realistic_listing = True
    form = valid_edit_form(operation)
    form["operation_type"] = "income"
    form["operation_date"] = "2026-07-18"
    form["description"] = "Новый доход"

    with TestClient(app) as client:
        response = client.post(
            f"{MANUAL_LEDGER_URL}/new",
            data=form,
            headers={"HX-Request": "true"},
        )

    created = calls.operations[-1]
    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#manual-ledger-results"
    assert response.headers["HX-Reswap"] == "outerHTML"
    assert response.headers["HX-Replace-Url"].startswith(f"{MANUAL_LEDGER_URL}?page=1&per_page=50")
    assert f'id="next-operation-{created.id}"' in response.text
    assert "workbench-row--target" in response.text
    assert "Новый доход" in response.text
    assert "2 ручные операции" in response.text
    assert 'id="manual-ledger-create"' in response.text
    assert 'hx-swap-oob="outerHTML"' in response.text
    assert 'id="next-manual-operation-create-form"' not in response.text
    assert response.text.count("data-disclosure-reset") == 3
    assert len(calls.income_expense_commands) == 1


def test_create_http_fallback_redirects_to_created_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]

    with TestClient(app) as client:
        response = client.post(
            f"{MANUAL_LEDGER_URL}/new",
            data=valid_edit_form(operation),
            follow_redirects=False,
        )

    created = calls.operations[-1]
    assert response.status_code == 303
    assert f"operation_id={created.id}" in response.headers["location"]
    assert response.headers["location"].endswith(f"#next-operation-{created.id}")


def test_create_transfer_dispatches_transfer_use_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_transfer()
    calls.operations = [operation]
    form = valid_edit_form(operation)
    assert operation.destination_entry is not None
    form["destination_account_id"] = str(operation.destination_entry.account_id)

    with TestClient(app) as client:
        response = client.post(
            f"{MANUAL_LEDGER_URL}/new",
            data=form,
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert calls.income_expense_commands == []
    assert len(calls.transfer_commands) == 1
    assert calls.transfer_commands[0].amount == Decimal("5000.00")


def test_create_requires_financial_write_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    context = workspace_context(role=WorkspaceRole.VIEWER)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    calls.operations = [manual_expense()]

    with TestClient(app) as client:
        response = client.get(
            f"{MANUAL_LEDGER_URL}/new",
            headers={"HX-Request": "true"},
        )

    assert response.status_code == 403
