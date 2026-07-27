from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.features.imports.application.documents.snapshot import (
    ImportDocumentSnapshot,
    ImportParseAttemptSnapshot,
    ImportRawTransactionRow,
)
from app.features.imports.domain.validation import MONEY_TOLERANCE
from app.features.imports.models import (
    ParseAttemptStatus,
    RawTransactionStatus,
    UploadedDocumentStatus,
)

DETAIL_ROW_LIMIT = 5
DETAIL_ATTEMPT_LIMIT = 10


class ImportDocumentWorkflowStepState(StrEnum):
    PENDING = "pending"
    CURRENT = "current"
    DONE = "done"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class ImportDocumentDetailNextStep(StrEnum):
    MAPPING = "mapping"
    REVIEW = "review"
    UPLOAD = "upload"
    DOCUMENT_LIST = "document_list"


class ImportDocumentActionBlockingReason(StrEnum):
    IMPORT_MANAGEMENT_FORBIDDEN = "import_management_forbidden"
    LINKED_OPERATIONS_EXIST = "linked_operations_exist"
    ALREADY_IGNORED = "already_ignored"


class ImportDocumentDetailValidationReasonCode(StrEnum):
    TOTALS_MATCH = "totals_match"
    ROWS_NEED_REVIEW = "rows_need_review"
    BALANCE_CHAIN_MISMATCH = "balance_chain_mismatch"
    CONTROL_TOTALS_UNAVAILABLE = "control_totals_unavailable"
    CONTROL_TOTALS_MISMATCH = "control_totals_mismatch"
    IGNORED_ROWS_EXPLAIN_MISMATCH = "ignored_rows_explain_mismatch"
    NEEDS_MAPPING = "needs_mapping"
    VALIDATION_FAILED = "validation_failed"


@dataclass(frozen=True)
class ImportDocumentDetailAccountDto:
    id: UUID
    name: str
    currency: str


@dataclass(frozen=True)
class ImportDocumentDetailWorkflowDto:
    upload: ImportDocumentWorkflowStepState
    extract: ImportDocumentWorkflowStepState
    mapping: ImportDocumentWorkflowStepState
    review: ImportDocumentWorkflowStepState
    ledger: ImportDocumentWorkflowStepState


@dataclass(frozen=True)
class ImportDocumentDetailValidationDto:
    status: str
    reason_code: ImportDocumentDetailValidationReasonCode
    message: str
    extracted_count: int | None
    calculated_total_inflow: str | None
    calculated_total_outflow: str | None
    ignored_row_count: int
    ignored_total_inflow: str | None
    ignored_total_outflow: str | None
    currency: str | None
    table_count: int | None
    needs_mapping: bool


@dataclass(frozen=True)
class ImportDocumentDetailRawRowDto:
    row_index: int
    status: RawTransactionStatus
    display_date: date | str | None
    amount: Decimal | None
    amount_raw: str | None
    currency: str | None
    description: str
    normalization_error: str


@dataclass(frozen=True)
class ImportDocumentDetailAttemptDto:
    id: UUID
    status: ParseAttemptStatus
    parser_name: str
    parser_version: str | None
    started_at: datetime
    finished_at: datetime | None
    message: str


@dataclass(frozen=True)
class ImportDocumentDetailCollectionDto[T]:
    items: tuple[T, ...]
    total: int
    limit: int


@dataclass(frozen=True)
class ImportDocumentActionCapabilityDto:
    allowed: bool
    blocking_reason_codes: tuple[ImportDocumentActionBlockingReason, ...]


@dataclass(frozen=True)
class ImportDocumentDetailCapabilitiesDto:
    can_manage: bool
    ignore: ImportDocumentActionCapabilityDto
    delete: ImportDocumentActionCapabilityDto


@dataclass(frozen=True)
class ImportDocumentDetailReadModel:
    id: UUID
    filename: str
    status: UploadedDocumentStatus
    bank_name: str | None
    statement_type: str | None
    statement_period_start: date | None
    statement_period_end: date | None
    file_size_bytes: int | None
    created_at: datetime | None
    updated_at: datetime | None
    account: ImportDocumentDetailAccountDto | None
    workflow: ImportDocumentDetailWorkflowDto
    next_step: ImportDocumentDetailNextStep
    validation: ImportDocumentDetailValidationDto | None
    raw_rows: ImportDocumentDetailCollectionDto[ImportDocumentDetailRawRowDto]
    parse_attempts: ImportDocumentDetailCollectionDto[ImportDocumentDetailAttemptDto]
    capabilities: ImportDocumentDetailCapabilitiesDto


class ImportDocumentSnapshotReader(Protocol):
    async def get_document_snapshot(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> ImportDocumentSnapshot | None: ...


class ImportDocumentDetailReader:
    def __init__(self, documents: ImportDocumentSnapshotReader) -> None:
        self._documents = documents

    async def read(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        can_manage: bool,
    ) -> ImportDocumentDetailReadModel | None:
        snapshot = await self._documents.get_document_snapshot(workspace_id, document_id)
        if snapshot is None:
            return None
        return self.from_snapshot(snapshot, can_manage=can_manage)

    @staticmethod
    def from_snapshot(
        snapshot: ImportDocumentSnapshot,
        *,
        can_manage: bool,
    ) -> ImportDocumentDetailReadModel:
        validation = _validation(snapshot.validation, rows=snapshot.raw_transactions)
        return ImportDocumentDetailReadModel(
            id=snapshot.id,
            filename=snapshot.original_filename,
            status=snapshot.status,
            bank_name=snapshot.bank_name,
            statement_type=snapshot.statement_type,
            statement_period_start=snapshot.statement_period_start,
            statement_period_end=snapshot.statement_period_end,
            file_size_bytes=snapshot.file_size_bytes,
            created_at=snapshot.created_at,
            updated_at=snapshot.updated_at,
            account=(
                ImportDocumentDetailAccountDto(
                    id=snapshot.account.id,
                    name=snapshot.account.name,
                    currency=snapshot.account.currency,
                )
                if snapshot.account is not None
                else None
            ),
            workflow=_workflow(snapshot, validation),
            next_step=_next_step(snapshot, validation, can_manage=can_manage),
            validation=validation,
            raw_rows=ImportDocumentDetailCollectionDto(
                items=tuple(_raw_row(row) for row in snapshot.raw_transactions[:DETAIL_ROW_LIMIT]),
                total=len(snapshot.raw_transactions),
                limit=DETAIL_ROW_LIMIT,
            ),
            parse_attempts=ImportDocumentDetailCollectionDto(
                items=tuple(
                    _attempt(attempt) for attempt in snapshot.parse_attempts[:DETAIL_ATTEMPT_LIMIT]
                ),
                total=len(snapshot.parse_attempts),
                limit=DETAIL_ATTEMPT_LIMIT,
            ),
            capabilities=_capabilities(snapshot, can_manage=can_manage),
        )


def _workflow(
    snapshot: ImportDocumentSnapshot,
    validation: ImportDocumentDetailValidationDto | None,
) -> ImportDocumentDetailWorkflowDto:
    state = ImportDocumentWorkflowStepState
    if snapshot.status is UploadedDocumentStatus.IMPORTED:
        return ImportDocumentDetailWorkflowDto(
            state.DONE, state.DONE, state.SKIPPED, state.DONE, state.DONE
        )
    if snapshot.status is UploadedDocumentStatus.IGNORED:
        return ImportDocumentDetailWorkflowDto(
            state.DONE, state.DONE, state.SKIPPED, state.SKIPPED, state.SKIPPED
        )
    if validation is not None and validation.needs_mapping:
        return ImportDocumentDetailWorkflowDto(
            state.DONE, state.DONE, state.CURRENT, state.PENDING, state.PENDING
        )
    if snapshot.raw_transactions:
        return ImportDocumentDetailWorkflowDto(
            state.DONE, state.DONE, state.SKIPPED, state.CURRENT, state.PENDING
        )
    if snapshot.status is UploadedDocumentStatus.FAILED_TO_PARSE:
        return ImportDocumentDetailWorkflowDto(
            state.DONE, state.BLOCKED, state.PENDING, state.PENDING, state.PENDING
        )
    return ImportDocumentDetailWorkflowDto(
        state.DONE, state.CURRENT, state.PENDING, state.PENDING, state.PENDING
    )


def _next_step(
    snapshot: ImportDocumentSnapshot,
    validation: ImportDocumentDetailValidationDto | None,
    *,
    can_manage: bool,
) -> ImportDocumentDetailNextStep:
    if snapshot.status is UploadedDocumentStatus.IGNORED:
        return ImportDocumentDetailNextStep.DOCUMENT_LIST
    if validation is not None and validation.needs_mapping and can_manage:
        return ImportDocumentDetailNextStep.MAPPING
    if snapshot.raw_transactions or snapshot.status is UploadedDocumentStatus.IMPORTED:
        return ImportDocumentDetailNextStep.REVIEW
    if snapshot.status is UploadedDocumentStatus.FAILED_TO_PARSE and can_manage:
        return ImportDocumentDetailNextStep.UPLOAD
    return ImportDocumentDetailNextStep.DOCUMENT_LIST


def _capabilities(
    snapshot: ImportDocumentSnapshot,
    *,
    can_manage: bool,
) -> ImportDocumentDetailCapabilitiesDto:
    permission = (
        () if can_manage else (ImportDocumentActionBlockingReason.IMPORT_MANAGEMENT_FORBIDDEN,)
    )
    linked = any(row.linked_operation_id is not None for row in snapshot.raw_transactions)
    linked_reasons = permission + (
        (ImportDocumentActionBlockingReason.LINKED_OPERATIONS_EXIST,) if linked else ()
    )
    ignore_reasons = linked_reasons + (
        (ImportDocumentActionBlockingReason.ALREADY_IGNORED,)
        if snapshot.status is UploadedDocumentStatus.IGNORED
        else ()
    )
    return ImportDocumentDetailCapabilitiesDto(
        can_manage=can_manage,
        ignore=ImportDocumentActionCapabilityDto(not ignore_reasons, ignore_reasons),
        delete=ImportDocumentActionCapabilityDto(not linked_reasons, linked_reasons),
    )


def _validation(
    report: dict[str, object] | None,
    *,
    rows: list[ImportRawTransactionRow],
) -> ImportDocumentDetailValidationDto | None:
    if report is None:
        return None
    status = _string(report.get("status"))
    return ImportDocumentDetailValidationDto(
        status=status,
        reason_code=_validation_reason_code(report, status=status),
        message=_string(report.get("message")),
        extracted_count=_integer(report.get("extracted_count")),
        calculated_total_inflow=_optional_string(report.get("calculated_total_inflow")),
        calculated_total_outflow=_optional_string(report.get("calculated_total_outflow")),
        ignored_row_count=sum(row.status is RawTransactionStatus.IGNORED for row in rows),
        ignored_total_inflow=_optional_string(report.get("ignored_total_inflow")),
        ignored_total_outflow=_optional_string(report.get("ignored_total_outflow")),
        currency=_optional_string(report.get("currency")),
        table_count=_integer(report.get("table_count")),
        needs_mapping=status == "needs_mapping",
    )


def _validation_reason_code(
    report: dict[str, object],
    *,
    status: str,
) -> ImportDocumentDetailValidationReasonCode:
    reason = ImportDocumentDetailValidationReasonCode
    if status == "needs_mapping":
        return reason.NEEDS_MAPPING
    if status == "failed":
        return reason.VALIDATION_FAILED
    if status == "needs_review":
        return reason.ROWS_NEED_REVIEW
    balance_chain = report.get("balance_chain")
    if isinstance(balance_chain, dict) and balance_chain.get("status") == "mismatch":
        return reason.BALANCE_CHAIN_MISMATCH
    if status == "unavailable":
        return reason.CONTROL_TOTALS_UNAVAILABLE
    if status == "mismatch":
        differences = (
            _optional_decimal(report.get("unexplained_inflow_difference")),
            _optional_decimal(report.get("unexplained_outflow_difference")),
        )
        comparable = [difference for difference in differences if difference is not None]
        if comparable and all(abs(difference) <= MONEY_TOLERANCE for difference in comparable):
            return reason.IGNORED_ROWS_EXPLAIN_MISMATCH
        return reason.CONTROL_TOTALS_MISMATCH
    return reason.TOTALS_MATCH


def _raw_row(row: ImportRawTransactionRow) -> ImportDocumentDetailRawRowDto:
    return ImportDocumentDetailRawRowDto(
        row_index=row.row_index,
        status=row.status,
        display_date=row.display_date,
        amount=row.amount,
        amount_raw=row.amount_raw,
        currency=row.currency,
        description=row.description,
        normalization_error=row.normalization_error,
    )


def _attempt(attempt: ImportParseAttemptSnapshot) -> ImportDocumentDetailAttemptDto:
    return ImportDocumentDetailAttemptDto(
        id=attempt.id,
        status=attempt.status,
        parser_name=attempt.parser_name,
        parser_version=attempt.parser_version,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        message=attempt.message,
    )


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _optional_string(value: object) -> str | None:
    return None if value is None or value == "" else str(value)


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _optional_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
