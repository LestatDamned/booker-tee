from app.features.imports.application.unknown_statements.column_dto import (
    UnknownStatementColumnCandidate,
    UnknownStatementColumnProfile,
)
from app.features.imports.application.unknown_statements.profile_helpers import (
    candidate_indexes_by_field,
    first_data_row_for_profiles,
    profile_for_column,
)
from app.features.imports.application.unknown_statements.suggestion_dto import (
    UnknownStatementMappingSuggestion,
    UnknownStatementMappingSuggestionWarning,
)
from app.features.imports.application.unknown_statements.suggestion_scoring import (
    confidence_for_field,
    reason_for_field,
)


def build_mapping_suggestions(
    profiles: list[UnknownStatementColumnProfile],
    candidates: list[UnknownStatementColumnCandidate],
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

    confidence_scores = [
        confidence_for_field(profile_for_column(profiles, column_index), field)
        for field, column_index in selected_fields
    ]
    confidence = sum(confidence_scores) / len(confidence_scores)
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
            first_data_row=first_data_row_for_profiles(profiles),
            confidence=round(confidence, 4),
            reasons=reasons,
            warnings=warnings,
        )
    ]
