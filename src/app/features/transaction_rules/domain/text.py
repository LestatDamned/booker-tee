from app.features.ledger.models import OperationType
from app.features.transaction_rules.errors import TransactionRuleError
from app.features.transaction_rules.models import TransactionRuleMatchType


def clean_rule_name(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def clean_rule_pattern(value: str | None) -> str:
    cleaned = clean_rule_name(value)
    if cleaned is None:
        raise TransactionRuleError("Rule pattern is required.")
    return cleaned[:255]


def clean_description(value: str | None) -> str | None:
    cleaned = clean_rule_name(value)
    return cleaned[:1000] if cleaned else None


def build_rule_name(
    *,
    pattern: str,
    match_type: TransactionRuleMatchType,
    category_name: str | None,
    target_operation_type: OperationType | None,
) -> str:
    target = clean_rule_name(category_name) or (
        target_operation_type.value if target_operation_type else None
    )
    if target:
        return f"{pattern} -> {target}"
    return f"{match_type.value}: {pattern}"


def normalized_text(value: str | None) -> str:
    tokens: list[str] = []
    token_chars: list[str] = []
    for char in (value or "").casefold():
        if char.isalnum():
            token_chars.append(char)
            continue
        if token_chars:
            tokens.append("".join(token_chars))
            token_chars = []
    if token_chars:
        tokens.append("".join(token_chars))
    return " ".join(token for token in tokens if not token.isdecimal())
