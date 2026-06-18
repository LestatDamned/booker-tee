from app.features.imports.application.unknown_statements.column_dto import (
    UnknownStatementColumnCandidate,
    UnknownStatementColumnProfile,
)
from app.features.imports.application.unknown_statements.header_keywords import (
    header_matches_for_cell,
)
from app.features.imports.application.unknown_statements.profile_helpers import (
    best_description_profile,
    best_profile,
    cell_at,
    column_label,
)
from app.features.imports.application.unknown_statements.row_detection import (
    clean_row,
    row_has_text,
    row_looks_like_header,
)
from app.features.imports.application.unknown_statements.value_detectors import (
    is_currency_like_cell,
    is_date_like_cell,
    is_description_like_cell,
    is_money_like_cell,
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
        if "operation_date" in profile.header_matches:
            candidates.append(
                column_candidate("operation_date", profile.column_index, profile.header, 0.95)
            )
        if "posting_date" in profile.header_matches:
            candidates.append(
                column_candidate("posting_date", profile.column_index, profile.header, 0.9)
            )
        if "description" in profile.header_matches:
            candidates.append(
                column_candidate("description", profile.column_index, profile.header, 0.9)
            )
        if "debit_amount" in profile.header_matches:
            candidates.append(
                column_candidate("debit_amount", profile.column_index, profile.header, 0.9)
            )
            continue
        if "credit_amount" in profile.header_matches:
            candidates.append(
                column_candidate("credit_amount", profile.column_index, profile.header, 0.9)
            )
            continue
        if "amount" in profile.header_matches:
            candidates.append(
                column_candidate("amount", profile.column_index, profile.header, 0.85)
            )
        if "currency" in profile.header_matches:
            candidates.append(
                column_candidate("currency", profile.column_index, profile.header, 0.85)
            )
        if "balance_after" in profile.header_matches:
            candidates.append(
                column_candidate("balance_after", profile.column_index, profile.header, 0.85)
            )
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
                0.75,
            )
        )
    if amount_profile is not None:
        candidates.append(
            column_candidate("amount", amount_profile.column_index, amount_profile.header, 0.7)
        )
    if description_profile is not None:
        candidates.append(
            column_candidate(
                "description",
                description_profile.column_index,
                description_profile.header,
                0.65,
            )
        )
    if currency_profile is not None:
        candidates.append(
            column_candidate(
                "currency", currency_profile.column_index, currency_profile.header, 0.65
            )
        )
    return candidates


def column_candidate(
    field: str,
    column_index: int,
    header: str,
    confidence: float,
) -> UnknownStatementColumnCandidate:
    return UnknownStatementColumnCandidate(
        field=field,
        column_index=column_index,
        header=header,
        confidence=confidence,
    )
