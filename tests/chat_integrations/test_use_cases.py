from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.features.chat_integrations.errors import ChatReviewActionError
from app.features.chat_integrations.use_cases import dashboard as chat_dashboard
from app.features.chat_integrations.use_cases.manual import parsing as chat_manual_parsing
from app.features.chat_integrations.use_cases.review import actions as chat_review_actions
from app.features.chat_integrations.use_cases.review import state as chat_review_state


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


def test_chat_manual_description_cleaner_removes_extra_spacing() -> None:
    assert chat_manual_parsing.ChatManualDescriptionCleaner.clean("  Обед   с семьей  ") == (
        "Обед с семьей"
    )
    assert chat_manual_parsing.ChatManualDescriptionCleaner.clean("   ") is None


def test_chat_review_action_mapper_supports_duplicate_action() -> None:
    assert chat_review_actions.ChatReviewActionMapper.to_review_status_action("dup") == "duplicate"
    assert chat_review_actions.ChatReviewActionMapper.to_action_label("dup") == (
        "строка помечена как дубль"
    )
