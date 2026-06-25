from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from app.features.categories.models import CategoryKind
from app.features.imports.infrastructure.extraction.pdfplumber_extractor import PdfPlumberExtractor
from app.features.imports.models import RawTransaction, RawTransactionStatus
from app.features.imports.parsing.parsers.expobank.card import ExpobankCardStatementParser
from app.features.ledger.models import OperationType
from app.features.transaction_rules.application.fixture_seeding import (
    DEFAULT_MERCHANT_RULE_SEEDS,
)
from app.features.transaction_rules.application.rule_application import select_best_matching_rule
from app.features.transaction_rules.domain.matching import rule_matches_raw_transaction
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


def test_contains_rule_matches_description_by_direction() -> None:
    workspace_id = uuid4()
    category_id = uuid4()
    rule = transaction_rule(
        workspace_id=workspace_id,
        category_id=category_id,
        pattern="krasnoe&beloe",
    )
    raw = make_raw_transaction(
        workspace_id=workspace_id,
        amount=Decimal("-743.75"),
        description="Списание в KRASNOE&BELOE по карте",
    )

    assert rule_matches_raw_transaction(rule, raw)

    raw.amount = Decimal("743.75")
    assert not rule_matches_raw_transaction(rule, raw)


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


def test_normalized_text_simplifies_merchant_noise() -> None:
    assert normalized_text("YANDEX*GO") == "yandex go"
    assert normalized_text("YANDEX 4121 GO") == "yandex go"
    assert normalized_text("SBER*5411*SAMOKA") == "sber samoka"
    assert normalized_text("wildberries.ru") == "wildberries ru"


def test_contains_rule_matches_noisy_yandex_go_variants() -> None:
    workspace_id = uuid4()
    rule = transaction_rule(
        workspace_id=workspace_id,
        category_id=uuid4(),
        pattern="YANDEX GO",
    )
    raw = make_raw_transaction(
        workspace_id=workspace_id,
        amount=Decimal("-320.00"),
        description="Оплата YANDEX*GO",
    )

    assert rule_matches_raw_transaction(rule, raw)

    raw.description_normalized = "YANDEX 4121 GO"
    assert rule_matches_raw_transaction(rule, raw)

    raw.description_normalized = "YANDEX PLUS"
    assert not rule_matches_raw_transaction(rule, raw)


def test_default_merchant_rule_suggests_products_for_krasnoe_beloe() -> None:
    workspace_id = uuid4()
    products_category_id = uuid4()
    extracted = PdfPlumberExtractor().extract(Path("tests/fixtures/expobank_statement.pdf"))
    drafts = ExpobankCardStatementParser().extract_raw_transactions(
        extracted,
        account_id=None,
        currency="RUB",
    )
    krasnoe_beloe_draft = drafts[1]
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
        amount=krasnoe_beloe_draft.amount,
        description=krasnoe_beloe_draft.description_normalized,
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


def test_default_merchant_rules_include_collected_user_patterns() -> None:
    seeds_by_pattern = {seed.pattern: seed for seed in DEFAULT_MERCHANT_RULE_SEEDS}

    assert seeds_by_pattern["FASOL"].category_name == "Продукты"
    assert seeds_by_pattern["T-Mobile"].category_name == "Связь и интернет"
    assert seeds_by_pattern["YANDEX GO"].category_name == "Такси"
    assert seeds_by_pattern["OZON"].category_name == "Маркетплейсы"
    assert seeds_by_pattern["wildberries.ru"].category_name == "Маркетплейсы"
    assert seeds_by_pattern["YANDEX PLUS"].category_name == "Подписки и сервисы"
    assert seeds_by_pattern["TELECOMA"].category_name == "Связь и интернет"
    assert seeds_by_pattern["ЕКАТЕРИНБУРГ ЯБЛОКО"].category_name == "Красота и здоровье"


def test_default_merchant_rule_patterns_are_normalized_unique() -> None:
    normalized_patterns = [normalized_text(seed.pattern) for seed in DEFAULT_MERCHANT_RULE_SEEDS]

    assert len(normalized_patterns) == len(set(normalized_patterns))


def transaction_rule(
    *,
    workspace_id: UUID,
    category_id: UUID | None,
    pattern: str,
    application_mode: TransactionRuleApplicationMode = TransactionRuleApplicationMode.SUGGEST,
) -> TransactionRule:
    return TransactionRule(
        id=uuid4(),
        workspace_id=workspace_id,
        name=f"{pattern} -> category",
        is_active=True,
        priority=100,
        match_type=TransactionRuleMatchType.CONTAINS,
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
