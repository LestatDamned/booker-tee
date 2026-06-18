from app.features.imports.application.unknown_statements.column_dto import (
    UnknownStatementColumnCandidate,
    UnknownStatementColumnProfile,
)


def candidate_indexes_by_field(
    candidates: list[UnknownStatementColumnCandidate],
) -> dict[str, int]:
    indexes: dict[str, int] = {}
    for candidate in candidates:
        indexes[candidate.field] = candidate.column_index
    return indexes


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
