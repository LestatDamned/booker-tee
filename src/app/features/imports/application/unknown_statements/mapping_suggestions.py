from app.features.imports.application.unknown_statements.analysis_models import (
    UnknownStatementColumnCandidate,
    UnknownStatementColumnProfile,
    UnknownStatementMappingSuggestion,
    UnknownStatementMappingSuggestionReason,
    UnknownStatementMappingSuggestionWarning,
)
from app.features.imports.application.unknown_statements.column_profiles import (
    candidate_indexes_by_field,
    first_data_row_for_profiles,
    profile_for_column,
)

FIELD_VALUE_EVIDENCE = {
    "operation_date": ("date_like_count", "date_like_values"),
    "posting_date": ("date_like_count", "date_like_values"),
    "amount": ("money_like_count", "money_like_values"),
    "debit_amount": ("money_like_count", "money_like_values"),
    "credit_amount": ("money_like_count", "money_like_values"),
    "currency": ("currency_like_count", "currency_like_values"),
    "balance_after": ("money_like_count", "money_like_values"),
    "description": ("description_like_count", "description_like_values"),
}


def build_mapping_suggestions(
    profiles: list[UnknownStatementColumnProfile],
    candidates: list[UnknownStatementColumnCandidate],
    *,
    row_offset: int = 0,
) -> list[UnknownStatementMappingSuggestion]:
    candidate_by_field = candidate_indexes_by_field(candidates)
    operation_date_column = candidate_by_field.get("operation_date")
    posting_date_column = candidate_by_field.get("posting_date")
    description_column = candidate_by_field.get("description")
    amount_column = candidate_by_field.get("amount")
    debit_amount_column = candidate_by_field.get("debit_amount")
    credit_amount_column = candidate_by_field.get("credit_amount")
    currency_column = candidate_by_field.get("currency")
    balance_after_column = candidate_by_field.get("balance_after")
    if operation_date_column is None or description_column is None:
        return []
    if amount_column is None and debit_amount_column is None and credit_amount_column is None:
        return []

    selected_fields: list[tuple[str, int]] = [
        ("operation_date", operation_date_column),
        ("description", description_column),
    ]
    warnings: list[UnknownStatementMappingSuggestionWarning] = []
    if amount_column is not None:
        selected_fields.append(("amount", amount_column))
    else:
        if debit_amount_column is not None:
            selected_fields.append(("debit_amount", debit_amount_column))
        if credit_amount_column is not None:
            selected_fields.append(("credit_amount", credit_amount_column))
        if debit_amount_column is None or credit_amount_column is None:
            warning_fields = []
            if debit_amount_column is not None:
                warning_fields.append("debit_amount")
            if credit_amount_column is not None:
                warning_fields.append("credit_amount")
            warnings.append(
                UnknownStatementMappingSuggestionWarning(
                    code="partial_debit_credit_columns",
                    fields=warning_fields,
                )
            )
    if currency_column is not None:
        selected_fields.append(("currency", currency_column))
    if balance_after_column is not None:
        selected_fields.append(("balance_after", balance_after_column))
    if posting_date_column is not None:
        selected_fields.append(("posting_date", posting_date_column))

    reasons = [
        reason_for_field(profile_for_column(profiles, column_index), field)
        for field, column_index in selected_fields
    ]
    return [
        UnknownStatementMappingSuggestion(
            operation_date_column=operation_date_column,
            posting_date_column=posting_date_column,
            description_column=description_column,
            amount_column=amount_column,
            debit_amount_column=debit_amount_column,
            credit_amount_column=credit_amount_column,
            currency_column=currency_column,
            balance_after_column=balance_after_column,
            first_data_row=row_offset + first_data_row_for_profiles(profiles),
            reasons=reasons,
            warnings=warnings,
        )
    ]


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
    count_field, evidence = FIELD_VALUE_EVIDENCE[field]
    matched_count = int(getattr(profile, count_field))
    return UnknownStatementMappingSuggestionReason(
        field=field,
        column_index=profile.column_index,
        header=profile.header,
        evidence=evidence,
        matched_count=matched_count,
        sample_count=profile.sample_count,
    )
