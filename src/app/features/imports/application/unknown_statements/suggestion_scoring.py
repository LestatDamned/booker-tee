from app.features.imports.application.unknown_statements.column_dto import (
    UnknownStatementColumnProfile,
)
from app.features.imports.application.unknown_statements.suggestion_dto import (
    UnknownStatementMappingSuggestionReason,
)


def confidence_for_field(profile: UnknownStatementColumnProfile, field: str) -> float:
    if field in profile.header_matches:
        return 0.95 if field == "operation_date" else 0.9
    sample_count = max(profile.sample_count, 1)
    if field in {"operation_date", "posting_date"}:
        return min(0.9, 0.55 + (profile.date_like_count / sample_count) * 0.35)
    if field in {"amount", "debit_amount", "credit_amount"}:
        return min(0.85, 0.5 + (profile.money_like_count / sample_count) * 0.35)
    if field == "currency":
        return min(0.8, 0.45 + (profile.currency_like_count / sample_count) * 0.35)
    if field == "balance_after":
        return min(0.8, 0.45 + (profile.money_like_count / sample_count) * 0.35)
    if field == "description":
        return min(0.85, 0.45 + (profile.description_like_count / sample_count) * 0.4)
    return 0.5


def reason_for_field(
    profile: UnknownStatementColumnProfile,
    field: str,
) -> UnknownStatementMappingSuggestionReason:
    if field in profile.header_matches:
        return UnknownStatementMappingSuggestionReason(
            field=field,
            column_index=profile.column_index,
            header=profile.header,
            evidence="header_match",
        )
    if field in {"operation_date", "posting_date"}:
        return UnknownStatementMappingSuggestionReason(
            field=field,
            column_index=profile.column_index,
            header=profile.header,
            evidence="date_like_values",
            matched_count=profile.date_like_count,
            sample_count=profile.sample_count,
        )
    if field in {"amount", "debit_amount", "credit_amount"}:
        return UnknownStatementMappingSuggestionReason(
            field=field,
            column_index=profile.column_index,
            header=profile.header,
            evidence="money_like_values",
            matched_count=profile.money_like_count,
            sample_count=profile.sample_count,
        )
    if field == "currency":
        return UnknownStatementMappingSuggestionReason(
            field=field,
            column_index=profile.column_index,
            header=profile.header,
            evidence="currency_like_values",
            matched_count=profile.currency_like_count,
            sample_count=profile.sample_count,
        )
    if field == "balance_after":
        return UnknownStatementMappingSuggestionReason(
            field=field,
            column_index=profile.column_index,
            header=profile.header,
            evidence="money_like_values",
            matched_count=profile.money_like_count,
            sample_count=profile.sample_count,
        )
    return UnknownStatementMappingSuggestionReason(
        field=field,
        column_index=profile.column_index,
        header=profile.header,
        evidence="description_like_values",
        matched_count=profile.description_like_count,
        sample_count=profile.sample_count,
    )
