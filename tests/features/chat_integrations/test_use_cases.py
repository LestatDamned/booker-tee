from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest

from app.features.chat_integrations.errors import ChatReviewActionError
from app.features.chat_integrations.use_cases import dashboard as chat_dashboard
from app.features.chat_integrations.use_cases.manual import parsing as chat_manual_parsing
from app.features.chat_integrations.use_cases.manual import progress as chat_manual_progress
from app.features.chat_integrations.use_cases.manual.dto import (
    StartedChatManualCategorySelection,
)
from app.features.chat_integrations.use_cases.review import actions as chat_review_actions
from app.features.chat_integrations.use_cases.review import builders as chat_review_builders
from app.features.chat_integrations.use_cases.review import state as chat_review_state
from app.features.import_review.domain.lifecycle import ImportReviewLifecycleAction
from app.features.import_review.schemas.commands import (
    LinkImportReviewExistingTransferCommand,
)
from app.features.ledger.models import OperationType


def test_account_balance_totals_do_not_mix_currencies() -> None:
    totals = chat_dashboard.ChatAccountBalanceTotalBuilder.build_totals(
        (
            chat_dashboard.ChatAccountBalanceRow(
                account_name="Карта",
                currency="RUB",
                balance=Decimal("10.00"),
            ),
            chat_dashboard.ChatAccountBalanceRow(
                account_name="Cash",
                currency="USD",
                balance=Decimal("3.50"),
            ),
            chat_dashboard.ChatAccountBalanceRow(
                account_name="Наличные",
                currency="RUB",
                balance=Decimal("20.00"),
            ),
        )
    )

    assert totals == (
        chat_dashboard.ChatCurrencyBalanceTotal(currency="RUB", balance=Decimal("30.00")),
        chat_dashboard.ChatCurrencyBalanceTotal(currency="USD", balance=Decimal("3.50")),
    )


def test_chat_month_range_handles_december() -> None:
    assert chat_dashboard.ChatMonthRange.next_month_start(date(2026, 12, 1)) == date(
        2027,
        1,
        1,
    )


@pytest.mark.asyncio
async def test_chat_review_state_claimer_allows_only_one_final_action() -> None:
    state = SimpleNamespace(consumed_at=None)
    claim_results = [True, False]

    class FakeChatIntegrationRepository:
        async def try_consume_active_conversation_state(self, claimed_state, **_kwargs):
            assert claimed_state is state
            return claim_results.pop(0)

    repository = FakeChatIntegrationRepository()

    await chat_review_state.ChatReviewStateClaimer.claim_once(
        cast(Any, repository),
        cast(Any, state),
    )

    with pytest.raises(ChatReviewActionError, match="Stored review action is invalid."):
        await chat_review_state.ChatReviewStateClaimer.claim_once(
            cast(Any, repository),
            cast(Any, state),
        )


def test_chat_manual_amount_parser_accepts_common_russian_money_format() -> None:
    assert chat_manual_parsing.ChatManualAmountParser.parse_positive_amount("1 250,50") == Decimal(
        "1250.50"
    )
    assert chat_manual_parsing.ChatManualAmountParser.parse_positive_amount("1250 руб") == Decimal(
        "1250.00"
    )


def test_chat_manual_date_parser_accepts_russian_and_iso_formats() -> None:
    assert chat_manual_parsing.ChatManualDateParser.parse("30.06.2026") == date(2026, 6, 30)
    assert chat_manual_parsing.ChatManualDateParser.parse("2026-06-30") == date(2026, 6, 30)


@pytest.mark.asyncio
async def test_chat_manual_progress_accepts_text_date_on_date_choice_step() -> None:
    state = SimpleNamespace(
        step="choose_date",
        flow="record_expense",
        state_payload={
            "operation_type": "expense",
            "amount": "1250.50",
            "currency": "RUB",
            "account_name": "Cash",
        },
    )
    replaced_steps: list[str] = []

    class FakeStates:
        async def get_latest_active(self, *, context: object) -> object:
            return state

        async def replace(
            self,
            *,
            context: object,
            state: Any,
            flow: object,
            step: str,
            payload: dict[str, object],
        ) -> str:
            replaced_steps.append(step)
            state.step = step
            state.state_payload = payload
            return "categorytoken"

    class FakeCategories:
        async def list_or_seed_defaults(
            self,
            workspace_id: object,
            workspace_type: object,
            *,
            include_inactive: bool,
        ) -> list[object]:
            return []

    result = await chat_manual_progress.ChatManualOperationProgressService(
        states=cast(Any, FakeStates()),
        categories=cast(Any, FakeCategories()),
    ).continue_from_text_input(
        context=cast(
            Any,
            SimpleNamespace(workspace=SimpleNamespace(id="workspace-id", type="personal")),
        ),
        text="30.06.2026",
    )

    assert replaced_steps == ["choose_category"]
    assert isinstance(result, StartedChatManualCategorySelection)
    assert result.operation_type == OperationType.EXPENSE
    assert result.amount == Decimal("1250.50")
    assert result.category_choices[0].name == "Без категории"


def test_chat_manual_description_cleaner_removes_extra_spacing() -> None:
    assert chat_manual_parsing.ChatManualDescriptionCleaner.clean("  Обед   с семьей  ") == (
        "Обед с семьей"
    )
    assert chat_manual_parsing.ChatManualDescriptionCleaner.clean("   ") is None


def test_chat_review_action_mapper_supports_duplicate_action() -> None:
    assert (
        chat_review_actions.ChatReviewActionMapper.to_lifecycle_action("dup")
        is ImportReviewLifecycleAction.MARK_DUPLICATE
    )
    assert chat_review_actions.ChatReviewActionMapper.to_action_label("dup") == (
        "строка помечена как дубль"
    )


def test_chat_review_transfer_command_builder_supports_existing_manual_transfer() -> None:
    document_id = "9b4fb082-c4e9-4e87-8592-b5ef8c17f7f9"
    raw_transaction_id = "7fc0447b-5dc6-45f1-80d5-45f16280bd4d"
    operation_id = "81011d3b-ec69-41a0-9454-a6aece29360f"
    idempotency_key = UUID("0ba3d29e-4f30-4692-b241-f62e610a8c95")

    command = chat_review_builders.ChatReviewTransferCommandBuilder.build_command(
        {
            "document_id": document_id,
            "raw_transaction_id": raw_transaction_id,
            "matched_operation_id": operation_id,
        },
        idempotency_key=idempotency_key,
    )

    assert str(command.document_id) == document_id
    assert isinstance(command, LinkImportReviewExistingTransferCommand)
    assert str(command.item_id) == raw_transaction_id
    assert str(command.operation_id) == operation_id
    assert command.idempotency_key == idempotency_key
