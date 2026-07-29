from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.features.imports.documents.dto import ImportDocumentSnapshot
from app.features.imports.mapping.control_totals import (
    ResolvedMappingControlTotal,
    resolve_mapping_control_totals,
)
from app.features.imports.mapping.dto import (
    MappedStatementRow,
    MappingBalanceReconciliationDto,
    MappingControlTotalKind,
    MappingPreviewRowDto,
    MappingResolvedControlTotalDto,
    MappingRowErrorCode,
    MappingTableRefDto,
    StatementMappingPreview,
    StatementMappingSpec,
    UnsignedAmountDirection,
)
from app.features.imports.mapping.engine import StatementMappingEngine
from app.features.imports.mapping.errors import StatementMappingUnavailableError
from app.features.imports.mapping.queries.overview import (
    latest_mapping_raw_tables,
    mapping_capability,
)
from app.features.imports.mapping.raw_tables import (
    compatible_mapping_tables,
    find_raw_table,
)
from app.features.imports.mapping.rows import explicit_amount_direction
from app.features.imports.mapping.validation import (
    StatementMappingValidator,
    raise_for_mapping_validation_issues,
)

MAX_MAPPING_PREVIEW_RESPONSE_ROWS = 20
MAX_MAPPING_PREVIEW_RAW_CHARS = 1_000
MAX_MAPPING_PREVIEW_DESCRIPTION_CHARS = 2_000
MAX_MAPPING_SOURCE_CELL_CHARS = 500


class MappingPreviewDocumentReader(Protocol):
    async def get_document_snapshot(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> ImportDocumentSnapshot | None: ...


class StatementMappingPreviewReader:
    def __init__(self, documents: MappingPreviewDocumentReader) -> None:
        self._documents = documents

    async def read(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        spec: StatementMappingSpec,
    ) -> StatementMappingPreview | None:
        snapshot = await self._documents.get_document_snapshot(workspace_id, document_id)
        if snapshot is None:
            return None
        raw_tables = latest_mapping_raw_tables(snapshot)
        capability = mapping_capability(snapshot, raw_tables)
        if not capability.allowed:
            raise StatementMappingUnavailableError(capability.blocking_reason_codes)
        selected_table = find_raw_table(
            raw_tables,
            page_number=spec.page_number,
            table_index=spec.table_index,
        )
        raise_for_mapping_validation_issues(
            StatementMappingValidator.validate(
                spec=spec,
                selected_table=selected_table,
                raw_tables=raw_tables,
            )
        )
        compatible_tables = compatible_mapping_tables(raw_tables, spec)
        result = StatementMappingEngine.apply(raw_tables, spec, max_rows=None)
        resolved_control_totals = resolve_mapping_control_totals(raw_tables, spec)
        rows = tuple(
            mapping_preview_row(row, spec)
            for row in result.rows[:MAX_MAPPING_PREVIEW_RESPONSE_ROWS]
        )
        return StatementMappingPreview(
            rows=rows,
            total_row_count=len(result.rows),
            valid_row_count=result.valid_count,
            invalid_row_count=result.error_count,
            row_limit=MAX_MAPPING_PREVIEW_RESPONSE_ROWS,
            rows_truncated=len(result.rows) > len(rows),
            compatible_tables=tuple(
                MappingTableRefDto(table.page_number, table.table_index)
                for table in compatible_tables
            ),
            warnings=tuple(result.warnings),
            control_totals=tuple(
                MappingResolvedControlTotalDto(
                    kind=total.kind,
                    cell=total.cell,
                    raw_value=total.raw_value[:MAX_MAPPING_SOURCE_CELL_CHARS],
                    amount=str(total.amount),
                    currency=spec.default_currency,
                )
                for total in resolved_control_totals
            ),
            reconciliation=_balance_reconciliation(
                result.rows,
                resolved_control_totals,
            ),
            can_import=result.valid_count > 0
            and not any(warning.severity == "error" for warning in result.warnings),
        )


def mapping_preview_row(
    row: MappedStatementRow,
    spec: StatementMappingSpec,
) -> MappingPreviewRowDto:
    return MappingPreviewRowDto(
        table_ref=MappingTableRefDto(row.page_number, row.table_index),
        source_row_number=row.source_row_number + 1,
        operation_date=row.operation_date,
        operation_date_raw=_bounded_raw(row.operation_date_raw),
        posting_date=row.posting_date,
        posting_date_raw=_bounded_raw(row.posting_date_raw),
        description=(row.description or row.description_raw)[
            :MAX_MAPPING_PREVIEW_DESCRIPTION_CHARS
        ],
        amount=str(row.amount) if row.amount is not None else None,
        amount_raw=_bounded_raw(row.amount_raw),
        currency=row.currency,
        balance_after=(str(row.balance_after) if row.balance_after is not None else None),
        balance_after_raw=_bounded_raw(row.balance_after_raw),
        status=row.status,
        error_codes=mapping_row_error_codes(row, spec),
    )


def mapping_row_error_codes(
    row: MappedStatementRow,
    spec: StatementMappingSpec,
) -> tuple[MappingRowErrorCode, ...]:
    codes: list[MappingRowErrorCode] = []
    if row.operation_date is None:
        codes.append(
            MappingRowErrorCode.OPERATION_DATE_REQUIRED
            if not row.operation_date_raw.strip()
            else MappingRowErrorCode.OPERATION_DATE_INVALID
        )
    if row.posting_date_raw.strip() and row.posting_date is None:
        codes.append(MappingRowErrorCode.POSTING_DATE_INVALID)
    if row.amount is None:
        codes.extend(_amount_error_codes(row, spec))
    if row.balance_after_raw.strip() and row.balance_after is None:
        codes.append(MappingRowErrorCode.BALANCE_AFTER_INVALID)
    if row.description is None:
        codes.append(MappingRowErrorCode.DESCRIPTION_REQUIRED)
    return tuple(codes)


def _amount_error_codes(
    row: MappedStatementRow,
    spec: StatementMappingSpec,
) -> list[MappingRowErrorCode]:
    if spec.amount_column is not None:
        if (
            row.amount_raw.strip()
            and spec.unsigned_amount_direction is UnsignedAmountDirection.REQUIRE_SIGN
            and explicit_amount_direction(row.amount_raw) is None
        ):
            return [MappingRowErrorCode.UNSIGNED_AMOUNT_DIRECTION_REQUIRED]
        return [
            MappingRowErrorCode.AMOUNT_REQUIRED
            if not row.amount_raw.strip()
            else MappingRowErrorCode.AMOUNT_INVALID
        ]
    debit_raw, credit_raw = _split_amount_raw(row.amount_raw)
    if debit_raw and credit_raw:
        return [MappingRowErrorCode.DEBIT_AND_CREDIT_PRESENT]
    if debit_raw:
        return [MappingRowErrorCode.DEBIT_INVALID]
    if credit_raw:
        return [MappingRowErrorCode.CREDIT_INVALID]
    return [MappingRowErrorCode.AMOUNT_REQUIRED]


def _split_amount_raw(value: str) -> tuple[str, str]:
    debit = ""
    credit = ""
    for part in value.split(" / "):
        if part.startswith("debit: "):
            debit = part.removeprefix("debit: ").strip()
        elif part.startswith("credit: "):
            credit = part.removeprefix("credit: ").strip()
    return debit, credit


def _bounded_raw(value: str) -> str:
    return value[:MAX_MAPPING_PREVIEW_RAW_CHARS]


def _balance_reconciliation(
    rows: list[MappedStatementRow],
    control_totals: tuple[ResolvedMappingControlTotal, ...],
) -> MappingBalanceReconciliationDto | None:
    opening = next(
        (
            total.amount
            for total in control_totals
            if total.kind is MappingControlTotalKind.OPENING_BALANCE
        ),
        None,
    )
    closing = next(
        (
            total.amount
            for total in control_totals
            if total.kind is MappingControlTotalKind.CLOSING_BALANCE
        ),
        None,
    )
    if opening is None or closing is None:
        return None
    movement = sum(
        (row.amount for row in rows if row.amount is not None),
        start=Decimal("0"),
    )
    calculated_closing = opening + movement
    difference = calculated_closing - closing
    return MappingBalanceReconciliationDto(
        opening_balance=str(opening),
        movement=str(movement),
        calculated_closing_balance=str(calculated_closing),
        statement_closing_balance=str(closing),
        difference=str(difference),
        matches=difference == 0,
    )
