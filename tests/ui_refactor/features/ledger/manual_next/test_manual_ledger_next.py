from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.accounts.models import AccountType
from app.features.ledger.application.commands import UpdateManualOperationCommand
from app.features.ledger.application.listing import (
    LedgerPage,
    LedgerPagination,
    ManualOperationFilters,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.mapping.dto import (
    AccountView,
    ManualOperationView,
    OperationRefMoneyEntryView,
)
from app.features.ledger.models import OperationStatus, OperationType
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.models import WorkspaceMemberStatus, WorkspaceRole
from app.features.workspaces.service import WorkspaceContext
from app.web.features.ledger.manual.forms import (
    ManualLedgerEditSubmission,
    validate_manual_ledger_edit,
)
from app.web.features.ledger.manual.presenter import ManualLedgerPresenter
from app.web.features.ledger.manual.query_state import (
    MANUAL_LEDGER_URL,
    safe_manual_ledger_return_to,
)
from app.web.features.ledger.manual.routes import router as manual_ledger_router
from app.web.templating import WEB_STATIC_ROOT
from app.web.ui.actions import DisclosureActionVM


def test_presenter_builds_server_owned_financial_and_action_contracts() -> None:
    operation = manual_expense()

    page = ManualLedgerPresenter().present(
        workspace_name="Дом",
        operations=[operation],
        page=LedgerPage(page=1, per_page=50, total=1),
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
    assert page.filters.active is False
    assert page.total_label == "1 ручная операция"


def test_presenter_keeps_transfer_separate_from_profit() -> None:
    operation = manual_transfer()

    page = ManualLedgerPresenter().present(
        workspace_name="Дом",
        operations=[operation],
        page=LedgerPage(page=1, per_page=50, total=1),
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
    assert "Операции можно исправлять прямо в строке" in response.text
    assert f'id="next-operation-{operation.id}"' in response.text
    assert "workbench-row--target" in response.text
    assert "money-value--expense" in response.text
    assert "src/app/static/css/app.css" not in response.text
    assert "financial-row" not in response.text
    assert 'option value="expense" selected' in response.text
    assert calls.workspace_ids == [context.workspace.id]
    assert calls.filters[0].operation_type is OperationType.EXPENSE
    assert calls.filters[0].status is OperationStatus.CONFIRMED
    assert calls.filters[0].search == "coffee"
    assert calls.paginations == [LedgerPagination(page=2, per_page=25)]


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
        fallback_page = client.get(fallback.headers["location"])

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
    assert "data-edit-panel" in panel_response.text
    assert "<html" not in panel_response.text
    assert fallback.status_code == 303
    assert "edit=" in fallback.headers["location"]
    assert fallback_page.status_code == 200
    assert f'id="next-manual-operation-form-{operation.id}"' in fallback_page.text
    assert 'x-data="disclosure(true)"' in fallback_page.text
    panel_opening_tag = fallback_page.text.split(
        f'id="next-manual-operation-edit-panel-{operation.id}"',
        maxsplit=1,
    )[1].split(">", maxsplit=1)[0]
    assert "x-cloak" not in panel_opening_tag
    assert 'href="/_next/ledger/manual?page=1&amp;per_page=50' in fallback_page.text


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
    assert f'id="next-manual-operation-form-{operation.id}"' in response.text
    assert 'value="bad-date"' in response.text
    assert "Выберите корректную дату" in response.text


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
    assert set(calls.updated_workspace_ids) == {context.workspace.id}


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


def test_edit_parser_rejects_same_transfer_accounts() -> None:
    account_id = uuid4()
    validation = validate_manual_ledger_edit(
        uuid4(),
        ManualLedgerEditSubmission(
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


def manual_expense() -> ManualOperationView:
    account = account_view("Карта")
    return ManualOperationView(
        id=uuid4(),
        type=OperationType.EXPENSE,
        status=OperationStatus.CONFIRMED,
        operation_date=date(2026, 7, 17),
        description="Кофе",
        category_id=None,
        property_id=None,
        category=None,
        property=None,
        primary_entry=OperationRefMoneyEntryView(
            account_id=account.id,
            account=account,
            amount=Decimal("-350.00"),
        ),
        source_entry=None,
        destination_entry=None,
        edit_amount=Decimal("350.00"),
    )


def manual_transfer() -> ManualOperationView:
    source = account_view("Карта")
    destination = account_view("Наличные")
    return ManualOperationView(
        id=uuid4(),
        type=OperationType.TRANSFER,
        status=OperationStatus.CONFIRMED,
        operation_date=date(2026, 7, 17),
        description="Снятие наличных",
        category_id=None,
        property_id=None,
        category=None,
        property=None,
        primary_entry=OperationRefMoneyEntryView(
            account_id=source.id,
            account=source,
            amount=Decimal("-5000.00"),
        ),
        source_entry=OperationRefMoneyEntryView(
            account_id=source.id,
            account=source,
            amount=Decimal("-5000.00"),
        ),
        destination_entry=OperationRefMoneyEntryView(
            account_id=destination.id,
            account=destination,
            amount=Decimal("5000.00"),
        ),
        edit_amount=Decimal("5000.00"),
    )


def account_view(name: str) -> AccountView:
    return AccountView(
        id=uuid4(),
        name=name,
        type=AccountType.CARD,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("0.00"),
    )


def valid_edit_form(operation: ManualOperationView) -> dict[str, str]:
    primary_entry = operation.primary_entry
    assert primary_entry is not None
    return {
        "operation_type": operation.type.value,
        "account_id": str(primary_entry.account_id),
        "destination_account_id": "",
        "amount": str(operation.edit_amount),
        "operation_date": operation.operation_date.isoformat(),
        "category_id": "",
        "property_id": "",
        "description": operation.description or "",
        "return_to": "/_next/ledger/manual?page=1&per_page=50",
    }


def workspace_context(
    *,
    role: WorkspaceRole,
    status: WorkspaceMemberStatus = WorkspaceMemberStatus.ACTIVE,
) -> WorkspaceContext:
    return cast(
        WorkspaceContext,
        SimpleNamespace(
            user=SimpleNamespace(id=uuid4(), email="user@example.com", is_active=True),
            workspace=SimpleNamespace(id=uuid4(), name="Дом", type="personal", is_active=True),
            membership=SimpleNamespace(role=role, status=status),
        ),
    )


def manual_operation_matches(
    operation: ManualOperationView,
    filters: ManualOperationFilters,
) -> bool:
    if filters.date_from is not None and operation.operation_date < filters.date_from:
        return False
    if filters.date_to is not None and operation.operation_date > filters.date_to:
        return False
    if filters.operation_type is not None and operation.type != filters.operation_type:
        return False
    if filters.status is not None and operation.status != filters.status:
        return False
    return not (
        filters.search and filters.search.casefold() not in (operation.description or "").casefold()
    )


class ManualLedgerCalls:
    def __init__(self) -> None:
        self.operations: list[ManualOperationView] = []
        self.page = LedgerPage(page=1, per_page=50, total=0)
        self.workspace_ids: list[UUID] = []
        self.filters: list[ManualOperationFilters] = []
        self.paginations: list[LedgerPagination] = []
        self.update_commands: list[UpdateManualOperationCommand] = []
        self.updated_workspace_ids: list[UUID] = []
        self.update_error: LedgerPostingError | None = None
        self.realistic_listing = False


def manual_ledger_app(
    monkeypatch: pytest.MonkeyPatch,
    *,
    context: WorkspaceContext,
) -> tuple[FastAPI, ManualLedgerCalls]:
    calls = ManualLedgerCalls()

    class FakeLedgerPostingService:
        def __init__(self, _session: AsyncSession) -> None:
            pass

        async def list_manual_operations(
            self,
            workspace_id: UUID,
            *,
            filters: ManualOperationFilters,
            pagination: LedgerPagination,
        ) -> tuple[list[ManualOperationView], LedgerPage]:
            calls.workspace_ids.append(workspace_id)
            calls.filters.append(filters)
            calls.paginations.append(pagination)
            if calls.realistic_listing:
                operations = [
                    operation
                    for operation in calls.operations
                    if manual_operation_matches(operation, filters)
                ]
                operations.sort(key=lambda operation: operation.operation_date, reverse=True)
                page = LedgerPage(
                    page=pagination.page,
                    per_page=pagination.per_page,
                    total=len(operations),
                )
                return operations[pagination.offset : pagination.offset + pagination.per_page], page
            return calls.operations, calls.page

        async def get_manual_operation(
            self,
            *,
            workspace_id: UUID,
            operation_id: UUID,
        ) -> ManualOperationView | None:
            calls.workspace_ids.append(workspace_id)
            return next(
                (operation for operation in calls.operations if operation.id == operation_id),
                None,
            )

        async def update_manual_operation(
            self,
            *,
            context: WorkspaceContext,
            command: UpdateManualOperationCommand,
        ) -> Any:
            calls.updated_workspace_ids.append(context.workspace.id)
            calls.update_commands.append(command)
            if calls.update_error is not None:
                raise calls.update_error
            operation = next(
                operation for operation in calls.operations if operation.id == command.operation_id
            )
            updated_operation = replace(
                operation,
                type=command.operation_type,
                operation_date=command.operation_date,
                description=command.description,
                category_id=command.category_id,
                property_id=command.property_id,
                edit_amount=command.amount,
            )
            calls.operations = [
                updated_operation if item.id == updated_operation.id else item
                for item in calls.operations
            ]
            return SimpleNamespace(id=command.operation_id)

    class FakeAccountService:
        def __init__(self, _session: AsyncSession) -> None:
            pass

        async def list_active_accounts(self, workspace_id: UUID) -> list[AccountView]:
            calls.workspace_ids.append(workspace_id)
            accounts: dict[UUID, AccountView] = {}
            for operation in calls.operations:
                for entry in (
                    operation.primary_entry,
                    operation.source_entry,
                    operation.destination_entry,
                ):
                    if entry is not None and entry.account is not None:
                        accounts[entry.account.id] = entry.account
            return list(accounts.values())

    class FakeCategoryService:
        def __init__(self, _session: AsyncSession) -> None:
            pass

        async def list_or_seed_defaults(
            self,
            workspace_id: UUID,
            _workspace_type: Any,
        ) -> list[Any]:
            calls.workspace_ids.append(workspace_id)
            return []

    class FakePropertyService:
        def __init__(self, _session: AsyncSession) -> None:
            pass

        async def list_active(self, workspace_id: UUID) -> list[Any]:
            calls.workspace_ids.append(workspace_id)
            return []

    async def session_override() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, object())

    async def context_override(request: Request) -> WorkspaceContext:
        request.state.workspace_context = context
        request.state.csrf_token = None
        return context

    monkeypatch.setattr(
        "app.web.features.ledger.manual.routes.LedgerPostingService",
        FakeLedgerPostingService,
    )
    monkeypatch.setattr(
        "app.web.features.ledger.manual.routes.AccountService",
        FakeAccountService,
    )
    monkeypatch.setattr(
        "app.web.features.ledger.manual.routes.CategoryService",
        FakeCategoryService,
    )
    monkeypatch.setattr(
        "app.web.features.ledger.manual.routes.PropertyService",
        FakePropertyService,
    )
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="src/app/static"), name="static")
    app.mount("/_next/static", StaticFiles(directory=WEB_STATIC_ROOT), name="web_static")
    app.include_router(manual_ledger_router)
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_settings] = lambda: Settings(environment="test")
    app.dependency_overrides[get_current_workspace_context] = context_override
    return app, calls
