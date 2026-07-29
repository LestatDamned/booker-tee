import re

from app.features.imports.mapping.analysis.dto import (
    UnknownStatementColumnCandidate,
    UnknownStatementColumnProfile,
    UnknownStatementMappingSuggestion,
    UnknownStatementMappingSuggestionReason,
    UnknownStatementMappingSuggestionWarning,
)
from app.features.imports.parsers.support.headers import (
    header_matches_for_cell,
)
from app.features.imports.parsers.support.normalization import DATE_PATTERNS

MONEY_PATTERN = re.compile(
    r"^(?:₽|\$|€|£)?\s*[+-]?\s*\d[\d\s]*(?:[,.]\d{2})\s*"
    r"(?:₽|руб\.?|rub|rur|usd|eur|gbp|cny|try|aed|\$|€|£)?$",
    flags=re.IGNORECASE,
)
SIGNED_INTEGER_MONEY_PATTERN = re.compile(
    r"^(?:₽|\$|€|£)?\s*[+-]\s*\d[\d\s]*"
    r"(?:₽|руб\.?|rub|rur|usd|eur|gbp|cny|try|aed|\$|€|£)?$",
    flags=re.IGNORECASE,
)
CURRENCY_PATTERN = re.compile(r"\b(?:rub|rur|usd|eur|gbp|cny|try|aed)\b|[₽$€£]")
SPLIT_AMOUNT_FIELDS = {"debit_amount", "credit_amount"}
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


def is_date_like_cell(value: str) -> bool:
    compacted = normalize_cell(value)
    if not compacted:
        return False
    return any(pattern.search(compacted) for pattern in DATE_PATTERNS)


def is_money_like_cell(value: str) -> bool:
    compacted = normalize_cell(value)
    if not compacted or not any(character.isdigit() for character in compacted):
        return False
    return bool(
        MONEY_PATTERN.fullmatch(compacted) or SIGNED_INTEGER_MONEY_PATTERN.fullmatch(compacted)
    )


def is_currency_like_cell(value: str) -> bool:
    compacted = normalize_cell(value)
    if not compacted:
        return False
    return bool(CURRENCY_PATTERN.fullmatch(compacted.casefold()))


def is_description_like_cell(value: str) -> bool:
    compacted = normalize_cell(value)
    if len(compacted) < 3 or is_currency_like_cell(compacted):
        return False
    if MONEY_PATTERN.fullmatch(compacted) or SIGNED_INTEGER_MONEY_PATTERN.fullmatch(compacted):
        return False
    return cell_has_letters(compacted)


def cell_has_letters(value: str) -> bool:
    return any(character.isalpha() for character in value)


def normalize_cell(value: str) -> str:
    return " ".join(value.split())


def clean_row(row: list[str | None]) -> list[str]:
    return [cell.strip() if cell else "" for cell in row]


def row_has_text(row: list[str]) -> bool:
    return any(cell for cell in row)


def row_looks_like_header(row: list[str]) -> bool:
    if row_looks_like_transaction(row):
        return False
    return any(header_matches_for_cell(cell) for cell in row)


def row_looks_like_transaction(row: list[str]) -> bool:
    return (
        any(is_date_like_cell(cell) for cell in row)
        and any(is_money_like_cell(cell) for cell in row)
        and any(cell_has_letters(cell) for cell in row)
    )


def build_column_profiles(table: list[list[str | None]]) -> list[UnknownStatementColumnProfile]:
    rows = [clean_row(row) for row in table if row_has_text(clean_row(row))]
    if not rows:
        return []
    has_header = row_looks_like_header(rows[0])
    header = rows[0] if has_header else []
    column_count = max((len(row) for row in rows), default=0)
    sample_rows = rows[1:11] if has_header else rows[:10]
    profiles: list[UnknownStatementColumnProfile] = []
    for index in range(column_count):
        values = [cell_at(row, index) for row in sample_rows]
        profiles.append(
            UnknownStatementColumnProfile(
                column_index=index,
                header=cell_at(header, index) or column_label(index),
                sample_count=len(values),
                non_empty_count=sum(1 for value in values if value.strip()),
                date_like_count=sum(1 for value in values if is_date_like_cell(value)),
                money_like_count=sum(1 for value in values if is_money_like_cell(value)),
                currency_like_count=sum(1 for value in values if is_currency_like_cell(value)),
                description_like_count=sum(
                    1 for value in values if is_description_like_cell(value)
                ),
                header_matches=header_matches_for_cell(cell_at(header, index))
                if has_header
                else [],
            )
        )
    return profiles


def infer_column_candidates_from_profiles(
    profiles: list[UnknownStatementColumnProfile],
) -> list[UnknownStatementColumnCandidate]:
    candidates: list[UnknownStatementColumnCandidate] = []
    for profile in profiles:
        for field in profile.header_matches:
            candidates.append(
                column_candidate(
                    field,
                    profile.column_index,
                    profile.header,
                )
            )
            if field in SPLIT_AMOUNT_FIELDS:
                break
    if candidates:
        return candidates
    return infer_columns_from_profiles_without_headers(profiles)


def infer_columns_from_profiles_without_headers(
    profiles: list[UnknownStatementColumnProfile],
) -> list[UnknownStatementColumnCandidate]:
    candidates: list[UnknownStatementColumnCandidate] = []
    date_profile = best_profile(profiles, "date_like_count")
    amount_profile = best_profile(profiles, "money_like_count")
    currency_profile = best_profile(profiles, "currency_like_count")
    excluded_columns = {
        profile.column_index for profile in (date_profile, amount_profile) if profile is not None
    }
    description_profile = best_description_profile(profiles, excluded_columns)

    if date_profile is not None:
        candidates.append(
            column_candidate(
                "operation_date",
                date_profile.column_index,
                date_profile.header,
            )
        )
    if amount_profile is not None:
        candidates.append(
            column_candidate("amount", amount_profile.column_index, amount_profile.header)
        )
    if description_profile is not None:
        candidates.append(
            column_candidate(
                "description",
                description_profile.column_index,
                description_profile.header,
            )
        )
    if currency_profile is not None:
        candidates.append(
            column_candidate(
                "currency",
                currency_profile.column_index,
                currency_profile.header,
            )
        )
    return candidates


def column_candidate(
    field: str,
    column_index: int,
    header: str,
) -> UnknownStatementColumnCandidate:
    return UnknownStatementColumnCandidate(
        field=field,
        column_index=column_index,
        header=header,
    )


def candidate_indexes_by_field(
    candidates: list[UnknownStatementColumnCandidate],
) -> dict[str, int]:
    return {candidate.field: candidate.column_index for candidate in candidates}


def profile_for_column(
    profiles: list[UnknownStatementColumnProfile],
    column_index: int,
) -> UnknownStatementColumnProfile:
    for profile in profiles:
        if profile.column_index == column_index:
            return profile
    return UnknownStatementColumnProfile(
        column_index=column_index,
        header=column_label(column_index),
        sample_count=0,
        non_empty_count=0,
        date_like_count=0,
        money_like_count=0,
        currency_like_count=0,
        description_like_count=0,
        header_matches=[],
    )


def first_data_row_for_profiles(profiles: list[UnknownStatementColumnProfile]) -> int:
    return 1 if any(profile.header_matches for profile in profiles) else 0


def best_profile(
    profiles: list[UnknownStatementColumnProfile],
    score_field: str,
) -> UnknownStatementColumnProfile | None:
    best: UnknownStatementColumnProfile | None = None
    best_score = 0
    for profile in profiles:
        score = int(getattr(profile, score_field))
        if score > best_score:
            best = profile
            best_score = score
    return best if best_score > 0 else None


def best_description_profile(
    profiles: list[UnknownStatementColumnProfile],
    excluded_columns: set[int],
) -> UnknownStatementColumnProfile | None:
    best: UnknownStatementColumnProfile | None = None
    best_score = 0
    for profile in profiles:
        if profile.column_index in excluded_columns:
            continue
        score = profile.description_like_count
        if score > best_score:
            best = profile
            best_score = score
    return best if best_score > 0 else None


def column_label(index: int) -> str:
    return f"column {index + 1}"


def cell_at(row: list[str], index: int) -> str:
    if index < 0 or index >= len(row):
        return ""
    return row[index]


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
    return UnknownStatementMappingSuggestionReason(
        field=field,
        column_index=profile.column_index,
        header=profile.header,
        evidence=evidence,
        matched_count=int(getattr(profile, count_field)),
        sample_count=profile.sample_count,
    )
