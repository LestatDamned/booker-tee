import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.features.imports.application.unknown_statement_mappings.dto import (
    MappingControlTotalCellRef,
    UnknownStatementMappingCommand,
)
from app.features.imports.application.unknown_statement_mappings.raw_tables import (
    find_raw_table,
    iter_raw_tables,
)
from app.features.imports.application.unknown_statements.hints import (
    control_total_label_sets_for_text,
    normalize_hint_text,
)
from app.features.imports.parsing.support.normalization import parse_money_amount

MONEY_FRAGMENT = re.compile(r"[+\-−]?\s*\d[\d\s\u00a0]*(?:[.,]\d{1,2})?")


class MappingControlTotalKind(StrEnum):
    OPENING_BALANCE = "opening_balance"
    CLOSING_BALANCE = "closing_balance"


@dataclass(frozen=True)
class MappingControlTotalCandidate:
    kind: MappingControlTotalKind
    cell: MappingControlTotalCellRef
    label: str
    raw_value: str
    amount: Decimal
    confidence: float


@dataclass(frozen=True)
class ResolvedMappingControlTotal:
    kind: MappingControlTotalKind
    cell: MappingControlTotalCellRef
    raw_value: str
    amount: Decimal


def detect_control_total_candidates(
    raw_tables: list[dict[str, object]] | None,
) -> tuple[MappingControlTotalCandidate, ...]:
    all_text = "\n".join(
        cell for table in iter_raw_tables(raw_tables) for row in table.rows for cell in row
    )
    label_sets = control_total_label_sets_for_text(all_text)
    labels_by_kind = {
        MappingControlTotalKind.OPENING_BALANCE: tuple(
            label for label_set in label_sets for label in label_set.opening_balance
        ),
        MappingControlTotalKind.CLOSING_BALANCE: tuple(
            label for label_set in label_sets for label in label_set.closing_balance
        ),
    }
    candidates: list[MappingControlTotalCandidate] = []
    for table in iter_raw_tables(raw_tables):
        for row_index, row in enumerate(table.rows):
            normalized_row = normalize_hint_text(" ".join(row))
            for kind, labels in labels_by_kind.items():
                label = next(
                    (
                        candidate
                        for candidate in labels
                        if normalize_hint_text(candidate) in normalized_row
                    ),
                    None,
                )
                if label is None:
                    continue
                money_cells = _money_cells(row)
                if len(money_cells) != 1:
                    continue
                column_index, raw_value, amount = money_cells[0]
                candidates.append(
                    MappingControlTotalCandidate(
                        kind=kind,
                        cell=MappingControlTotalCellRef(
                            page_number=table.page_number,
                            table_index=table.table_index,
                            row_number=row_index,
                            column_index=column_index,
                        ),
                        label=label,
                        raw_value=raw_value,
                        amount=amount,
                        confidence=0.98,
                    )
                )
    return tuple(_unique_candidates(candidates))


def automatic_control_total_cell(
    candidates: tuple[MappingControlTotalCandidate, ...],
    kind: MappingControlTotalKind,
) -> MappingControlTotalCellRef | None:
    matching = [candidate for candidate in candidates if candidate.kind is kind]
    return matching[0].cell if len(matching) == 1 else None


def resolve_control_total_cell(
    raw_tables: list[dict[str, object]] | None,
    *,
    kind: MappingControlTotalKind,
    cell: MappingControlTotalCellRef | None,
) -> ResolvedMappingControlTotal | None:
    if cell is None:
        return None
    table = find_raw_table(
        raw_tables,
        page_number=cell.page_number,
        table_index=cell.table_index,
    )
    if cell.row_number < 0 or cell.row_number >= len(table):
        return None
    row = table[cell.row_number]
    if cell.column_index < 0 or cell.column_index >= len(row):
        return None
    raw_value = row[cell.column_index]
    amount = money_from_cell(raw_value)
    if amount is None:
        return None
    return ResolvedMappingControlTotal(
        kind=kind,
        cell=cell,
        raw_value=raw_value,
        amount=amount,
    )


def resolve_mapping_control_totals(
    raw_tables: list[dict[str, object]] | None,
    command: UnknownStatementMappingCommand,
) -> tuple[ResolvedMappingControlTotal, ...]:
    return tuple(
        resolved
        for kind, cell in (
            (MappingControlTotalKind.OPENING_BALANCE, command.opening_balance_cell),
            (MappingControlTotalKind.CLOSING_BALANCE, command.closing_balance_cell),
        )
        if (
            resolved := resolve_control_total_cell(
                raw_tables,
                kind=kind,
                cell=cell,
            )
        )
        is not None
    )


def money_from_cell(value: str) -> Decimal | None:
    fragments = MONEY_FRAGMENT.findall(value.replace("\u00a0", " "))
    parsed: list[Decimal] = []
    for fragment in fragments:
        try:
            amount = parse_money_amount(fragment)
        except ValueError:
            continue
        if amount is not None:
            parsed.append(amount)
    return parsed[0] if len(parsed) == 1 else None


def _money_cells(row: list[str]) -> list[tuple[int, str, Decimal]]:
    cells: list[tuple[int, str, Decimal]] = []
    for index, value in enumerate(row):
        amount = money_from_cell(value)
        if amount is not None:
            cells.append((index, value, amount))
    return cells


def _unique_candidates(
    candidates: list[MappingControlTotalCandidate],
) -> list[MappingControlTotalCandidate]:
    seen: set[tuple[MappingControlTotalKind, int, int, int, int]] = set()
    unique: list[MappingControlTotalCandidate] = []
    for candidate in candidates:
        key = (
            candidate.kind,
            candidate.cell.page_number,
            candidate.cell.table_index,
            candidate.cell.row_number,
            candidate.cell.column_index,
        )
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique
