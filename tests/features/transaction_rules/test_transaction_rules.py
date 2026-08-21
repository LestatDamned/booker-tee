from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest

from app.features.categories.models import CategoryKind
from app.features.imports.models import RawTransaction
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.models import OperationType
from app.features.transaction_rules.application.fixture_seeding import (
    DEFAULT_MERCHANT_RULE_SEEDS,
)
from app.features.transaction_rules.application.rule_application import select_best_matching_rule
from app.features.transaction_rules.domain.matching import (
    can_suggest_raw_transaction,
    rule_matches_raw_transaction,
)
from app.features.transaction_rules.domain.patterns import infer_rule_pattern
from app.features.transaction_rules.domain.suggestions import (
    apply_rule_suggestion,
    rule_suggestion_auto_applies,
)
from app.features.transaction_rules.domain.text import normalized_text
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRule,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        pytest.param(Decimal("-743.75"), True, id="outflow"),
        pytest.param(Decimal("743.75"), False, id="inflow"),
    ],
)
def test_contains_rule_matches_description_by_direction(
    amount: Decimal,
    expected: bool,
) -> None:
    workspace_id = uuid4()
    category_id = uuid4()
    rule = transaction_rule(
        workspace_id=workspace_id,
        category_id=category_id,
        pattern="krasnoe&beloe",
    )
    raw = make_raw_transaction(
        workspace_id=workspace_id,
        amount=amount,
        description="Списание в KRASNOE&BELOE по карте",
    )

    assert rule_matches_raw_transaction(rule, raw) is expected


def test_rule_does_not_match_transaction_from_another_workspace() -> None:
    rule = transaction_rule(
        workspace_id=uuid4(),
        category_id=uuid4(),
        pattern="KRASNOE&BELOE",
    )
    raw = make_raw_transaction(
        workspace_id=uuid4(),
        amount=Decimal("-743.75"),
        description="Списание в KRASNOE&BELOE по карте",
    )

    assert rule_matches_raw_transaction(rule, raw) is False


@pytest.mark.parametrize(
    ("same_account", "expected"),
    [
        pytest.param(True, True, id="matching-account"),
        pytest.param(False, False, id="different-account"),
    ],
)
def test_account_rule_only_matches_its_account(
    same_account: bool,
    expected: bool,
) -> None:
    workspace_id = uuid4()
    rule = transaction_rule(
        workspace_id=workspace_id,
        category_id=uuid4(),
        pattern="KRASNOE&BELOE",
    )
    rule.account_id = uuid4()
    raw = make_raw_transaction(
        workspace_id=workspace_id,
        amount=Decimal("-743.75"),
        description="Списание в KRASNOE&BELOE по карте",
    )
    raw.account_id = rule.account_id if same_account else uuid4()

    assert rule_matches_raw_transaction(rule, raw) is expected


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        pytest.param(Decimal("-99.99"), False, id="below-minimum"),
        pytest.param(Decimal("-100.00"), True, id="at-minimum"),
        pytest.param(Decimal("-200.00"), True, id="at-maximum"),
        pytest.param(Decimal("-200.01"), False, id="above-maximum"),
    ],
)
def test_rule_amount_range_is_inclusive(amount: Decimal, expected: bool) -> None:
    workspace_id = uuid4()
    rule = transaction_rule(
        workspace_id=workspace_id,
        category_id=uuid4(),
        pattern="KRASNOE&BELOE",
    )
    rule.amount_min = Decimal("100.00")
    rule.amount_max = Decimal("200.00")
    raw = make_raw_transaction(
        workspace_id=workspace_id,
        amount=amount,
        description="Списание в KRASNOE&BELOE по карте",
    )

    assert rule_matches_raw_transaction(rule, raw) is expected


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        pytest.param("YANDEX*GO", True, id="normalized-exact-match"),
        pytest.param("Оплата YANDEX GO", False, id="contains-only"),
    ],
)
def test_exact_rule_requires_complete_normalized_description(
    description: str,
    expected: bool,
) -> None:
    workspace_id = uuid4()
    rule = transaction_rule(
        workspace_id=workspace_id,
        category_id=uuid4(),
        pattern="YANDEX GO",
        match_type=TransactionRuleMatchType.EXACT,
    )
    raw = make_raw_transaction(
        workspace_id=workspace_id,
        amount=Decimal("-320.00"),
        description=description,
    )

    assert rule_matches_raw_transaction(rule, raw) is expected


@pytest.mark.parametrize(
    ("status", "linked", "expected"),
    [
        pytest.param(RawTransactionStatus.EXTRACTED, False, False, id="extracted"),
        pytest.param(RawTransactionStatus.NORMALIZED, False, True, id="normalized"),
        pytest.param(RawTransactionStatus.SUGGESTED, False, True, id="suggested"),
        pytest.param(RawTransactionStatus.NEEDS_REVIEW, False, True, id="needs-review"),
        pytest.param(RawTransactionStatus.MATCHED, False, True, id="matched"),
        pytest.param(RawTransactionStatus.IGNORED, False, False, id="ignored"),
        pytest.param(RawTransactionStatus.DUPLICATE, False, False, id="duplicate"),
        pytest.param(
            RawTransactionStatus.POSSIBLE_DUPLICATE,
            False,
            True,
            id="possible-duplicate",
        ),
        pytest.param(RawTransactionStatus.FAILED, False, False, id="failed"),
        pytest.param(RawTransactionStatus.CONFIRMED, False, False, id="confirmed"),
        pytest.param(RawTransactionStatus.NORMALIZED, True, False, id="linked"),
    ],
)
def test_rule_suggestions_only_target_reviewable_unlinked_rows(
    status: RawTransactionStatus,
    linked: bool,
    expected: bool,
) -> None:
    raw = make_raw_transaction(
        workspace_id=uuid4(),
        amount=Decimal("-320.00"),
        description="YANDEX GO",
    )
    raw.status = status
    raw.linked_operation_id = uuid4() if linked else None

    assert can_suggest_raw_transaction(raw) is expected


def test_apply_rule_suggestion_prefills_raw_transaction() -> None:
    workspace_id = uuid4()
    category_id = uuid4()
    rule = transaction_rule(
        workspace_id=workspace_id,
        category_id=category_id,
        pattern="KRASNOE&BELOE",
    )
    raw = make_raw_transaction(
        workspace_id=workspace_id,
        amount=Decimal("-743.75"),
        description="Списание в KRASNOE&BELOE по карте",
    )

    apply_rule_suggestion(raw, rule)

    assert raw.status == RawTransactionStatus.SUGGESTED
    assert raw.suggested_category_id == category_id
    assert raw.suggested_operation_type == OperationType.EXPENSE
    assert raw.suggested_by_rule_id == rule.id
    suggestion = cast(dict[str, object], raw.raw_payload["rule_suggestion"])
    assert isinstance(suggestion, dict)
    assert suggestion["pattern"] == "KRASNOE&BELOE"
    assert suggestion["application_mode"] == "suggest"
    assert suggestion["category_id"] == str(category_id)
    assert suggestion["operation_type"] == "expense"
    assert rule_suggestion_auto_applies(raw) is False


def test_auto_apply_rule_marks_payload_mode() -> None:
    workspace_id = uuid4()
    rule = transaction_rule(
        workspace_id=workspace_id,
        category_id=uuid4(),
        pattern="KRASNOE&BELOE",
        application_mode=TransactionRuleApplicationMode.AUTO_APPLY,
    )
    raw = make_raw_transaction(
        workspace_id=workspace_id,
        amount=Decimal("-743.75"),
        description="Списание в KRASNOE&BELOE по карте",
    )

    apply_rule_suggestion(raw, rule)

    suggestion = cast(dict[str, object], raw.raw_payload["rule_suggestion"])
    assert suggestion["application_mode"] == "auto_apply"
    assert rule_suggestion_auto_applies(raw) is True


def test_infer_rule_pattern_extracts_expobank_merchant() -> None:
    raw = make_raw_transaction(
        workspace_id=uuid4(),
        amount=Decimal("-743.75"),
        description=(
            "Списание средств по транзакции № 1 от 27/05/2026 "
            "в KRASNOE&BELOE по карте 220147XXXXXX5017 | АО ЭКСПОБАНК"
        ),
    )

    assert infer_rule_pattern(raw) == "KRASNOE&BELOE"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("YANDEX*GO", "yandex go", id="separator"),
        pytest.param("YANDEX 4121 GO", "yandex go", id="terminal-code"),
        pytest.param("SBER*5411*SAMOKA", "sber samoka", id="mcc-code"),
        pytest.param("wildberries.ru", "wildberries ru", id="domain-separator"),
    ],
)
def test_normalized_text_simplifies_merchant_noise(value: str, expected: str) -> None:
    assert normalized_text(value) == expected


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        pytest.param("Оплата YANDEX*GO", True, id="separator"),
        pytest.param("YANDEX 4121 GO", True, id="terminal-code"),
        pytest.param("YANDEX PLUS", False, id="different-service"),
    ],
)
def test_contains_rule_matches_noisy_yandex_go_variants(
    description: str,
    expected: bool,
) -> None:
    workspace_id = uuid4()
    rule = transaction_rule(
        workspace_id=workspace_id,
        category_id=uuid4(),
        pattern="YANDEX GO",
    )
    raw = make_raw_transaction(
        workspace_id=workspace_id,
        amount=Decimal("-320.00"),
        description=description,
    )

    assert rule_matches_raw_transaction(rule, raw) is expected


def test_default_merchant_rule_suggests_products_for_krasnoe_beloe() -> None:
    workspace_id = uuid4()
    products_category_id = uuid4()
    rule_seed = next(
        seed for seed in DEFAULT_MERCHANT_RULE_SEEDS if seed.pattern == "KRASNOE&BELOE"
    )
    rule = transaction_rule(
        workspace_id=workspace_id,
        category_id=products_category_id,
        pattern=rule_seed.pattern,
    )
    raw = make_raw_transaction(
        workspace_id=workspace_id,
        amount=Decimal("-743.75"),
        description="Card purchase | KRASNOE&BELOE",
    )

    assert rule_seed.category_name == "Продукты"
    assert rule_seed.category_kind == CategoryKind.EXPENSE
    assert rule_matches_raw_transaction(rule, raw)


def test_matching_prefers_categorized_rule_over_legacy_categoryless_rule() -> None:
    workspace_id = uuid4()
    products_category_id = uuid4()
    categoryless_rule = transaction_rule(
        workspace_id=workspace_id,
        category_id=None,
        pattern="SAMOKA",
        application_mode=TransactionRuleApplicationMode.AUTO_APPLY,
    )
    products_rule = transaction_rule(
        workspace_id=workspace_id,
        category_id=products_category_id,
        pattern="SAMOKA",
        application_mode=TransactionRuleApplicationMode.AUTO_APPLY,
    )
    raw = make_raw_transaction(
        workspace_id=workspace_id,
        amount=Decimal("-1335.00"),
        description="SBER*5411*SAMOKA T по карте",
    )

    selected_rule = select_best_matching_rule([categoryless_rule, products_rule], raw)

    assert selected_rule is products_rule


@pytest.mark.parametrize(
    ("pattern", "expected_category"),
    [
        pytest.param("FASOL", "Продукты", id="fasol"),
        pytest.param("T-Mobile", "Связь и интернет", id="t-mobile"),
        pytest.param("YANDEX GO", "Такси", id="yandex-go"),
        pytest.param("OZON", "Маркетплейсы", id="ozon"),
        pytest.param("wildberries.ru", "Маркетплейсы", id="wildberries"),
        pytest.param("YANDEX PLUS", "Подписки и сервисы", id="yandex-plus"),
        pytest.param("TELECOMA", "Связь и интернет", id="telecoma"),
        pytest.param("ЕКАТЕРИНБУРГ ЯБЛОКО", "Красота и здоровье", id="yabloko"),
    ],
)
def test_default_merchant_rule_uses_expected_category(
    pattern: str,
    expected_category: str,
) -> None:
    seeds_by_pattern = {seed.pattern: seed for seed in DEFAULT_MERCHANT_RULE_SEEDS}

    assert seeds_by_pattern[pattern].category_name == expected_category


def test_default_merchant_rule_patterns_are_normalized_unique() -> None:
    normalized_patterns = [normalized_text(seed.pattern) for seed in DEFAULT_MERCHANT_RULE_SEEDS]

    assert len(normalized_patterns) == len(set(normalized_patterns))


def transaction_rule(
    *,
    workspace_id: UUID,
    category_id: UUID | None,
    pattern: str,
    application_mode: TransactionRuleApplicationMode = TransactionRuleApplicationMode.SUGGEST,
    match_type: TransactionRuleMatchType = TransactionRuleMatchType.CONTAINS,
) -> TransactionRule:
    return TransactionRule(
        id=uuid4(),
        workspace_id=workspace_id,
        name=f"{pattern} -> category",
        is_active=True,
        priority=100,
        match_type=match_type,
        pattern=pattern,
        application_mode=application_mode,
        direction=MoneyDirection.OUTFLOW,
        target_operation_type=OperationType.EXPENSE,
        category_id=category_id,
        affects_profit=True,
    )


def make_raw_transaction(
    *,
    workspace_id: UUID,
    amount: Decimal | None,
    description: str | None,
) -> RawTransaction:
    return RawTransaction(
        workspace_id=workspace_id,
        uploaded_document_id=uuid4(),
        parse_attempt_id=uuid4(),
        row_index=0,
        status=RawTransactionStatus.NORMALIZED,
        raw_payload={},
        amount=amount,
        currency="RUB",
        description_normalized=description,
    )
