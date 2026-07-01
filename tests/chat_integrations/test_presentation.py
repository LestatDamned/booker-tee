from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from app.features.chat_integrations.presentation.dashboard import TelegramDashboardPresenter
from app.features.chat_integrations.presentation.review import TelegramReviewPresenter
from app.features.chat_integrations.presentation.workspace import TelegramWorkspacePresenter
from app.features.chat_integrations.schemas import (
    ChatConversation,
    ChatConversationType,
    ChatProviderCode,
)
from app.features.chat_integrations.use_cases import dashboard as chat_dashboard
from app.features.chat_integrations.use_cases import workspace as chat_workspace
from app.features.chat_integrations.use_cases.review import dto as chat_review_dto
from app.features.workspaces.service import WorkspaceContext


def private_conversation() -> ChatConversation:
    return ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )


def workspace_context() -> WorkspaceContext:
    return WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=uuid4(), name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )


def review_item(
    status: str = "needs_review",
    *,
    row_index: int = 0,
    document_label: str | None = None,
    normalization_error: str | None = None,
    suggested_category_id: UUID | None = None,
    suggested_category_name: str | None = None,
) -> chat_review_dto.ChatReviewQueueItem:
    return chat_review_dto.ChatReviewQueueItem(
        document_id=uuid4(),
        raw_transaction_id=uuid4(),
        row_index=row_index,
        status=status,
        account_name="T-Bank Card",
        operation_date=date(2026, 6, 30),
        amount=Decimal("-1250.00"),
        amount_raw=None,
        currency="RUB",
        description="MAGNIT",
        suggested_operation_type="expense",
        normalization_error=normalization_error,
        suggested_category_id=suggested_category_id,
        suggested_category_name=suggested_category_name,
        document_label=document_label,
    )


def test_review_item_shows_duplicate_action_only_for_possible_duplicate() -> None:
    possible_duplicate = TelegramReviewPresenter.show_next_item(
        private_conversation(),
        review_item("possible_duplicate"),
        action_token="reviewtoken",
    )
    needs_review = TelegramReviewPresenter.show_next_item(
        private_conversation(),
        review_item("needs_review"),
        action_token="reviewtoken",
    )

    assert possible_duplicate.buttons[1][0].callback_data == "rev:reviewtoken:dup"
    assert possible_duplicate.buttons[1][1].text == "✅ Не дубль"
    assert possible_duplicate.buttons[1][1].callback_data == "rev:reviewtoken:uniq"
    assert needs_review.buttons[1][0].text == "🚫 Не учитывать"
    assert all(
        button.callback_data != "rev:reviewtoken:dup"
        for row in needs_review.buttons
        for button in row
    )
    assert all(
        button.callback_data != "rev:reviewtoken:uniq"
        for row in needs_review.buttons
        for button in row
    )


def test_review_item_shows_accept_suggestion_when_category_is_suggested() -> None:
    response = TelegramReviewPresenter.show_next_item(
        private_conversation(),
        review_item(
            suggested_category_id=uuid4(),
            suggested_category_name="Продукты",
        ),
        action_token="reviewtoken",
    )

    assert response.buttons[0][0].text == "✅ Принять"
    assert response.buttons[0][0].callback_data == "rev:reviewtoken:sug"
    assert response.buttons[0][1].text == "🏷 Категория"
    assert response.buttons[0][1].callback_data == "rev:reviewtoken:conf"
    assert response.buttons[1][0].callback_data == "rev:reviewtoken:trn"


def test_review_category_menu_uses_pages_and_global_category_indexes() -> None:
    category_choices = tuple(
        chat_review_dto.ChatReviewCategoryChoice(id=uuid4(), name=f"Категория {index}")
        for index in range(7, 14)
    )

    response = TelegramReviewPresenter.show_category_menu(
        private_conversation(),
        chat_review_dto.StartedChatReviewCategorySelection(
            action_token="categorytoken",
            item=review_item(),
            category_choices=category_choices,
            page_index=1,
            page_count=3,
            page_start_index=7,
        ),
    )

    assert "Страница 2 из 3" in response.text
    assert response.buttons[0][0].callback_data == "rvc:categorytoken:7"
    assert response.buttons[6][0].callback_data == "rvc:categorytoken:13"
    assert response.buttons[7][0].callback_data == "rcp:categorytoken:0"
    assert response.buttons[7][1].callback_data == "rcp:categorytoken:2"
    assert response.buttons[8][0].text == "🔎 К строке"
    assert response.buttons[8][0].callback_data == "rvb:categorytoken"


def test_review_document_selection_shows_statement_choices() -> None:
    first_document_id = uuid4()
    second_document_id = uuid4()

    response = TelegramReviewPresenter.show_document_selection(
        private_conversation(),
        chat_review_dto.StartedChatReviewDocumentSelection(
            action_token="documenttoken",
            document_choices=(
                chat_review_dto.ChatReviewDocumentChoice(
                    id=first_document_id,
                    label="june.pdf (T-Bank / card)",
                    reviewable_count=4,
                ),
                chat_review_dto.ChatReviewDocumentChoice(
                    id=second_document_id,
                    label="may.pdf",
                    reviewable_count=2,
                ),
            ),
        ),
    )

    assert "Проверка выписки" in response.text
    assert "1. june.pdf (T-Bank / card) - к проверке: 4" in response.text
    assert "2. may.pdf - к проверке: 2" in response.text
    assert response.buttons[0][0].callback_data == "rvd:documenttoken:0"
    assert response.buttons[1][0].callback_data == "rvd:documenttoken:1"
    assert response.buttons[2][0].callback_data == "main:menu"


def test_review_action_error_shows_friendly_stale_button_message() -> None:
    response = TelegramReviewPresenter.show_action_error(
        private_conversation(),
        "This review action expired. Open the next row again.",
    )

    assert "Кнопка устарела" in response.text
    assert "This review action expired" not in response.text
    assert response.buttons[0][0].text == "🔎 Актуальная строка"
    assert response.buttons[0][0].callback_data == "review:next"
    assert response.buttons[0][1].callback_data == "main:menu"
    assert response.callback_notification == "Кнопка устарела"


def test_review_action_error_keeps_non_stale_details() -> None:
    response = TelegramReviewPresenter.show_action_error(
        private_conversation(),
        "No active categories are available.",
    )

    assert "Не получилось применить действие" in response.text
    assert "No active categories are available." in response.text
    assert response.callback_notification == "Не получилось"


def test_review_rule_suggestion_shows_best_pattern_and_alternative_action() -> None:
    response = TelegramReviewPresenter.show_rule_suggestion(
        private_conversation(),
        chat_review_dto.StartedChatReviewRuleSuggestion(
            action_token="ruletoken",
            action_label="операция подтверждена",
            pattern="KRASNOE&BELOE",
            alternative_patterns=("KRASNOE",),
            category_name="Продукты",
        ),
    )

    assert "Запомнить для похожих операций?" in response.text
    assert "Признак: KRASNOE&BELOE" in response.text
    assert "Категория: Продукты" in response.text
    assert response.buttons[0][0].callback_data == "rvr:ruletoken:save"
    assert response.buttons[0][1].callback_data == "rvr:ruletoken:skip"
    assert response.buttons[1][0].callback_data == "rvr:ruletoken:pick"
    assert response.buttons[2][0].callback_data == "rvr:ruletoken:type"


def test_review_rule_pattern_menu_shows_pattern_choices() -> None:
    response = TelegramReviewPresenter.show_rule_pattern_menu(
        private_conversation(),
        chat_review_dto.StartedChatReviewRulePatternSelection(
            action_token="ruletoken",
            pattern_choices=("KRASNOE&BELOE", "KRASNOE"),
            category_name="Продукты",
        ),
    )

    assert "Выбери признак" in response.text
    assert response.buttons[0][0].callback_data == "rvq:ruletoken:0"
    assert response.buttons[1][0].callback_data == "rvq:ruletoken:1"
    assert response.buttons[2][0].callback_data == "rvr:ruletoken:type"
    assert response.buttons[3][0].callback_data == "rvr:ruletoken:skip"


def test_review_rule_pattern_input_asks_for_manual_pattern() -> None:
    response = TelegramReviewPresenter.show_rule_pattern_input(
        private_conversation(),
        chat_review_dto.StartedChatReviewRulePatternInput(
            action_token="ruletoken",
            category_name="Продукты",
        ),
    )

    assert "Напиши признак" in response.text
    assert "KRASNOE&BELOE" in response.text
    assert response.buttons[0][0].callback_data == "rvr:ruletoken:skip"


def test_review_item_formats_human_readable_status_and_hint() -> None:
    text = TelegramReviewPresenter.show_next_item(
        private_conversation(),
        review_item(
            "possible_duplicate",
            row_index=1,
            document_label="june.pdf (T-Bank / card)",
            normalization_error="Same account, date, amount, and currency.",
        ),
        action_token="reviewtoken",
    ).text

    assert "📄 Выписка: june.pdf (T-Bank / card)" in text
    assert "⚠️ Статус: возможный дубль" in text
    assert "🧭 Похоже на: расход" in text
    assert "👉 Что сделать: проверь: это дубль или не дубль" in text
    assert "❗ Почему нужно проверить: Same account, date, amount, and currency." in text


def test_workspace_menu_shows_current_and_available_workspaces() -> None:
    response = TelegramWorkspacePresenter.show_menu(
        private_conversation(),
        chat_workspace.StartedChatWorkspaceSelection(
            action_token="worktoken",
            workspace_choices=(
                chat_workspace.ChatWorkspaceChoice(
                    id=uuid4(),
                    name="Личное",
                    is_current=True,
                ),
                chat_workspace.ChatWorkspaceChoice(
                    id=uuid4(),
                    name="Бизнес",
                    is_current=False,
                ),
            ),
        ),
    )

    assert "Рабочее пространство" in response.text
    assert response.buttons[0][0].text == "✅ Личное"
    assert response.buttons[0][0].callback_data == "wsp:worktoken:0"
    assert response.buttons[1][0].text == "🗂️ Бизнес"
    assert response.buttons[1][0].callback_data == "wsp:worktoken:1"
    assert response.buttons[2][0].callback_data == "main:menu"


def test_monthly_summary_shows_financial_totals_and_review_counter() -> None:
    response = TelegramDashboardPresenter.show_monthly_summary(
        private_conversation(),
        workspace_context(),
        chat_dashboard.ChatMonthlySummary(
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
            currency="RUB",
            income=Decimal("100000.00"),
            expense=Decimal("40000.50"),
            profit=Decimal("59999.50"),
            documents_needing_attention=1,
            raw_transactions_needing_attention=4,
        ),
    )

    assert "📊 Сводка" in response.text
    assert "🗂️ Family" in response.text
    assert "01.07.2026–31.07.2026" in response.text
    assert "Доход: 100000.00 RUB" in response.text
    assert "Расход: 40000.50 RUB" in response.text
    assert "Итог: 59999.50 RUB" in response.text
    assert "К проверке: 5" in response.text
    assert response.buttons[0][0].callback_data == "sum:2026-06"
    assert response.buttons[0][1].text == "Июль 2026"
    assert response.buttons[0][1].callback_data == "sum:2026-07"
    assert response.buttons[0][2].callback_data == "sum:2026-08"
    assert response.buttons[1][0].callback_data == "sumc:2026-07"
    assert response.buttons[2][0].callback_data == "review:choose"
    assert response.buttons[2][1].callback_data == "balances:show"
    assert response.buttons[3][0].callback_data == "workspace:choose"
    assert response.buttons[4][0].callback_data == "main:menu"


def test_account_balances_show_totals_and_accounts() -> None:
    response = TelegramDashboardPresenter.show_account_balances(
        private_conversation(),
        workspace_context(),
        chat_dashboard.ChatAccountBalances(
            rows=(
                chat_dashboard.ChatAccountBalanceRow(
                    account_name="Карта",
                    currency="RUB",
                    balance=Decimal("25000.00"),
                ),
                chat_dashboard.ChatAccountBalanceRow(
                    account_name="Наличные",
                    currency="RUB",
                    balance=Decimal("5000.50"),
                ),
                chat_dashboard.ChatAccountBalanceRow(
                    account_name="Deposit",
                    currency="USD",
                    balance=Decimal("100.00"),
                ),
            ),
            totals=(
                chat_dashboard.ChatCurrencyBalanceTotal(
                    currency="RUB",
                    balance=Decimal("30000.50"),
                ),
                chat_dashboard.ChatCurrencyBalanceTotal(
                    currency="USD",
                    balance=Decimal("100.00"),
                ),
            ),
        ),
    )

    assert "💳 Балансы" in response.text
    assert "🗂️ Family" in response.text
    assert "Итого:" in response.text
    assert "30000.50 RUB" in response.text
    assert "100.00 USD" in response.text
    assert "Карта: 25000.00 RUB" in response.text
    assert "Наличные: 5000.50 RUB" in response.text
    assert response.buttons[0][0].callback_data == "summary:show"
    assert response.buttons[0][1].callback_data == "balances:show"
    assert response.buttons[1][0].callback_data == "workspace:choose"
    assert response.buttons[2][0].callback_data == "main:menu"


def test_category_summary_shows_category_details_for_period() -> None:
    response = TelegramDashboardPresenter.show_category_summary(
        private_conversation(),
        workspace_context(),
        chat_dashboard.ChatCategorySummary(
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
            currency="RUB",
            rows=(
                chat_dashboard.ChatCategorySummaryRow(
                    category_name="Аренда",
                    income=Decimal("100000.00"),
                    expense=Decimal("0.00"),
                    profit=Decimal("100000.00"),
                ),
                chat_dashboard.ChatCategorySummaryRow(
                    category_name="Продукты",
                    income=Decimal("0.00"),
                    expense=Decimal("40000.50"),
                    profit=Decimal("-40000.50"),
                ),
                chat_dashboard.ChatCategorySummaryRow(
                    category_name="Возвраты",
                    income=Decimal("1000.00"),
                    expense=Decimal("300.00"),
                    profit=Decimal("700.00"),
                ),
            ),
        ),
    )

    assert "🏷 Категории" in response.text
    assert "01.07.2026–31.07.2026" in response.text
    assert "Аренда: +100000.00 RUB" in response.text
    assert "Продукты: -40000.50 RUB" in response.text
    assert "Возвраты: +1000.00 RUB / -300.00 RUB / = 700.00 RUB" in response.text
    assert response.buttons[0][0].callback_data == "sum:2026-07"
    assert response.buttons[0][1].callback_data == "balances:show"
    assert response.buttons[1][0].callback_data == "main:menu"


def test_category_summary_shows_all_category_rows() -> None:
    response = TelegramDashboardPresenter.show_category_summary(
        private_conversation(),
        workspace_context(),
        chat_dashboard.ChatCategorySummary(
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
            currency="RUB",
            rows=tuple(
                chat_dashboard.ChatCategorySummaryRow(
                    category_name=f"Категория {index}",
                    income=Decimal("0.00"),
                    expense=Decimal(index),
                    profit=-Decimal(index),
                )
                for index in range(1, 13)
            ),
        ),
    )

    assert "Категория 1: -1.00 RUB" in response.text
    assert "Категория 12: -12.00 RUB" in response.text
    assert "еще категорий" not in response.text
