from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.features.imports.models import RawTransactionStatus
from app.features.imports.presentation.review.actions import ReviewActionPolicy
from app.features.imports.presentation.review.models import ActionSetVM, ClassificationVM
from app.features.imports.presentation.review.page import ReviewValidationPresenter
from app.features.imports.presentation.review.state import (
    ReviewConfirmabilityPolicy,
    ReviewStateResolver,
)
from app.features.ledger.models import OperationType


def review_row(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": uuid4(),
        "status": RawTransactionStatus.NEEDS_REVIEW,
        "operation_date": "2026-05-27",
        "operation_date_raw": None,
        "amount": Decimal("-100.00"),
        "currency": "RUB",
        "source_account_id": uuid4(),
        "account_id": None,
        "counterparty_account_id": None,
        "normalization_error": None,
        "raw_payload": {},
        "linked_operation_id": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def review_document(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {"id": uuid4(), "account_id": uuid4()}
    values.update(overrides)
    return SimpleNamespace(**values)


def category(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {"id": uuid4(), "name": "Категория", "system_key": None}
    values.update(overrides)
    return SimpleNamespace(**values)


def action_set_action_count(actions: ActionSetVM) -> int:
    return int(actions.primary is not None) + int(actions.visible_secondary is not None)


def assert_action_layout_contract(actions: ActionSetVM) -> None:
    assert action_set_action_count(actions) <= 2
    if actions.primary is not None:
        assert actions.primary.placement == "primary"
    if actions.visible_secondary is not None:
        assert actions.visible_secondary.placement == "secondary"
    for action in actions.danger:
        assert action.placement == "danger"
        assert action.style == "danger"
        assert action.confirm_message


@pytest.mark.parametrize(
    ("visual_state", "is_confirmable"),
    [
        ("ready_to_confirm", True),
        ("suggested", True),
        ("needs_review", False),
        ("possible_duplicate", False),
        ("duplicate", False),
        ("ignored", False),
        ("confirmed", False),
        ("matched", False),
    ],
)
def test_review_action_policy_keeps_primary_secondary_and_danger_contract(
    visual_state: str,
    is_confirmable: bool,
) -> None:
    linked_operation_id = uuid4() if visual_state in {"confirmed", "matched", "duplicate"} else None
    row = review_row(linked_operation_id=linked_operation_id)
    actions = ReviewActionPolicy(document_id=uuid4()).actions_for(
        row,
        visual_state=visual_state,
        is_confirmable=is_confirmable,
        category_panel_id="category-panel",
        transfer_panel_id="transfer-panel",
        category_id=uuid4(),
        property_id=None,
    )

    assert_action_layout_contract(actions)


def test_review_action_policy_confirmable_action_posts_confirm_with_selected_category() -> None:
    document_id = uuid4()
    row_id = uuid4()
    category_id = uuid4()
    property_id = uuid4()
    actions = ReviewActionPolicy(document_id=document_id).actions_for(
        review_row(id=row_id),
        visual_state="ready_to_confirm",
        is_confirmable=True,
        category_panel_id="category-panel",
        transfer_panel_id="transfer-panel",
        category_id=category_id,
        property_id=property_id,
    )

    assert actions.primary is not None
    assert actions.primary.id == "confirm"
    assert actions.primary.action_type == "post"
    assert (
        actions.primary.url == f"/imports/documents/{document_id}/raw-transactions/{row_id}/status"
    )
    assert actions.primary.hidden_fields == {
        "action": "confirm",
        "category_id": str(category_id),
        "property_id": str(property_id),
    }
    assert actions.visible_secondary is not None
    assert actions.visible_secondary.action_type == "panel_toggle"


def test_posted_review_action_policy_only_allows_undo_posting() -> None:
    document_id = uuid4()
    row_id = uuid4()
    operation_id = uuid4()
    actions = ReviewActionPolicy(document_id=document_id).actions_for(
        review_row(id=row_id, linked_operation_id=operation_id),
        visual_state="confirmed",
        is_confirmable=False,
        category_panel_id="category-panel",
        transfer_panel_id="transfer-panel",
        category_id=None,
        property_id=None,
    )

    assert actions.primary is None
    assert actions.visible_secondary is None
    assert actions.menu == []
    assert len(actions.danger) == 1
    undo_action = actions.danger[0]
    assert undo_action.id == "undo_posting"
    assert undo_action.label == "Отменить проведение"
    assert undo_action.action_type == "post"
    assert (
        undo_action.url
        == f"/imports/documents/{document_id}/raw-transactions/{row_id}/undo-posting"
    )
    assert undo_action.confirm_message


def test_review_action_policy_panel_toggle_actions_do_not_mutate_data() -> None:
    actions = ReviewActionPolicy(document_id=uuid4()).actions_for(
        review_row(),
        visual_state="needs_review",
        is_confirmable=False,
        category_panel_id="category-panel",
        transfer_panel_id="transfer-panel",
        category_id=None,
        property_id=None,
    )

    assert actions.primary is not None
    assert actions.primary.action_type == "panel_toggle"
    assert actions.primary.panel_id == "category-panel"
    assert actions.primary.url is None
    assert actions.primary.hidden_fields is None
    assert actions.visible_secondary is not None
    assert actions.visible_secondary.action_type == "panel_toggle"
    assert actions.visible_secondary.panel_id == "transfer-panel"
    assert actions.visible_secondary.url is None
    assert actions.visible_secondary.hidden_fields is None


def test_possible_duplicate_actions_are_status_actions_without_panel_toggle() -> None:
    document_id = uuid4()
    row_id = uuid4()
    actions = ReviewActionPolicy(document_id=document_id).actions_for(
        review_row(id=row_id),
        visual_state="possible_duplicate",
        is_confirmable=False,
        category_panel_id="category-panel",
        transfer_panel_id="transfer-panel",
        category_id=None,
        property_id=None,
    )

    assert actions.primary is not None
    assert actions.primary.id == "mark_unique"
    assert actions.primary.action_type == "post"
    assert actions.primary.hidden_fields == {"action": "mark_unique"}
    assert (
        actions.primary.url == f"/imports/documents/{document_id}/raw-transactions/{row_id}/status"
    )
    assert actions.visible_secondary is not None
    assert actions.visible_secondary.id == "needs_review"
    assert actions.visible_secondary.action_type == "post"
    rendered_actions = [
        action
        for action in (
            actions.primary,
            actions.visible_secondary,
            *actions.menu,
            *actions.danger,
        )
        if action is not None
    ]
    assert all(action.action_type != "panel_toggle" for action in rendered_actions)


def test_income_or_expense_without_real_category_is_not_confirmable() -> None:
    uncategorized = category(system_key="uncategorized")
    policy = ReviewConfirmabilityPolicy(categories=[uncategorized])

    problems_without_category = policy.check(
        review_row(),
        document=review_document(),
        classification=ClassificationVM(OperationType.EXPENSE, "explicit"),
        selected_category_id=None,
    )
    problems_with_uncategorized = policy.check(
        review_row(),
        document=review_document(),
        classification=ClassificationVM(OperationType.INCOME, "explicit"),
        selected_category_id=uncategorized.id,
    )

    assert "для дохода или расхода нужна категория" in problems_without_category
    assert "для дохода или расхода нужна категория" in problems_with_uncategorized


def test_income_or_expense_with_real_category_is_confirmable() -> None:
    groceries = category()

    problems = ReviewConfirmabilityPolicy(categories=[groceries]).check(
        review_row(),
        document=review_document(),
        classification=ClassificationVM(OperationType.EXPENSE, "explicit"),
        selected_category_id=groceries.id,
    )

    assert problems == []


@pytest.mark.parametrize(
    ("source_account_id", "counterparty_account_id", "expected_problem"),
    [
        (None, uuid4(), "для перевода нужны два счета"),
        (uuid4(), None, "для перевода нужны два счета"),
    ],
)
def test_transfer_requires_source_and_counterparty_accounts(
    source_account_id: UUID | None,
    counterparty_account_id: UUID | None,
    expected_problem: str,
) -> None:
    problems = ReviewConfirmabilityPolicy(categories=[]).check(
        review_row(
            source_account_id=source_account_id,
            counterparty_account_id=counterparty_account_id,
        ),
        document=review_document(account_id=None),
        classification=ClassificationVM(OperationType.TRANSFER, "explicit"),
        selected_category_id=None,
    )

    assert expected_problem in problems


def test_transfer_requires_different_accounts() -> None:
    account_id = uuid4()

    problems = ReviewConfirmabilityPolicy(categories=[]).check(
        review_row(source_account_id=account_id, counterparty_account_id=account_id),
        document=review_document(account_id=None),
        classification=ClassificationVM(OperationType.TRANSFER, "explicit"),
        selected_category_id=None,
    )

    assert "счета перевода должны отличаться" in problems


def test_transfer_with_two_different_accounts_is_confirmable() -> None:
    problems = ReviewConfirmabilityPolicy(categories=[]).check(
        review_row(source_account_id=uuid4(), counterparty_account_id=uuid4()),
        document=review_document(account_id=None),
        classification=ClassificationVM(OperationType.TRANSFER, "explicit"),
        selected_category_id=None,
    )

    assert problems == []


def test_ready_to_confirm_is_presentation_only_state() -> None:
    row = review_row(status=RawTransactionStatus.NEEDS_REVIEW)

    visual_state = ReviewStateResolver().resolve(row, is_confirmable=True)

    assert visual_state == "ready_to_confirm"
    assert row.status == RawTransactionStatus.NEEDS_REVIEW


def test_review_validation_presenter_prepares_summary_and_warning() -> None:
    summary = ReviewValidationPresenter().build(
        {
            "status": "mismatch",
            "message": "Остатки после операций не совпадают с суммами строк.",
            "extracted_count": 2,
            "needs_review_count": 1,
            "currency": "RUB",
            "calculated_total_inflow": "100.00",
            "calculated_total_outflow": "30.00",
            "ignored_total_inflow": "10.00",
            "ignored_total_outflow": "5.00",
            "statement_total_inflow": None,
            "statement_total_outflow": None,
            "inflow_difference": None,
            "outflow_difference": "10.00",
            "unexplained_inflow_difference": "0.00",
            "unexplained_outflow_difference": "10.00",
        }
    )

    assert summary is not None
    assert summary.status_label == "mismatch"
    assert summary.statement_total_inflow == "нет"
    assert summary.statement_total_outflow == "нет"
    assert summary.inflow_difference == "нет"
    assert summary.outflow_difference == "10.00"
    assert summary.ignored_total_inflow == "10.00"
    assert summary.ignored_total_outflow == "5.00"
    assert summary.unexplained_inflow_difference == "0.00"
    assert summary.unexplained_outflow_difference == "10.00"
    assert summary.warning_message is not None
    assert [(metric.label, metric.value) for metric in summary.metrics] == [
        ("проверка", "mismatch"),
        ("строки", 2),
        ("нужна проверка", 1),
        ("валюта", "RUB"),
    ]
    assert [row.kind for row in summary.control_total_rows] == ["Приход", "Расход"]
    assert [cell.label for cell in summary.control_total_rows[0].cells] == [
        "к учету",
        "исключено",
        "выписка",
        "не объяснено",
    ]
    assert summary.control_total_rows[0].cells[0].tone == "income"
    assert summary.control_total_rows[0].cells[1].tone == "excluded"
    assert summary.control_total_rows[0].cells[3].tone == "balanced"
    assert summary.control_total_rows[1].cells[0].tone == "expense"
    assert summary.control_total_rows[1].cells[1].tone == "excluded"
    assert summary.control_total_rows[1].cells[3].tone == "unexplained"
    assert "суммы или остатки не сходятся" in summary.warning_message


def test_review_validation_presenter_treats_ignored_rows_as_explained() -> None:
    summary = ReviewValidationPresenter().build(
        {
            "status": "mismatch",
            "message": "Итоги по строкам не совпадают с итогами выписки.",
            "extracted_count": 4,
            "needs_review_count": 0,
            "currency": "RUB",
            "calculated_total_inflow": "50.00",
            "calculated_total_outflow": "20.00",
            "ignored_total_inflow": "50.00",
            "ignored_total_outflow": "30.00",
            "statement_total_inflow": "100.00",
            "statement_total_outflow": "50.00",
            "inflow_difference": "-50.00",
            "outflow_difference": "-30.00",
            "unexplained_inflow_difference": "0.00",
            "unexplained_outflow_difference": "0.00",
        }
    )

    assert summary is not None
    assert summary.warning_message is None
    assert [cell.value for cell in summary.control_total_rows[0].cells] == [
        "50.00",
        "50.00",
        "100.00",
        "0.00",
    ]
    assert [cell.value for cell in summary.control_total_rows[1].cells] == [
        "20.00",
        "30.00",
        "50.00",
        "0.00",
    ]
