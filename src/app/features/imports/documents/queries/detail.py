"""Read one imported document."""

from typing import Protocol
from uuid import UUID

from app.features.imports.documents.dto import (
    ImportDocumentActionBlockingReason,
    ImportDocumentActionCapabilityDto,
    ImportDocumentDetailAttemptDto,
    ImportDocumentDetailCapabilitiesDto,
    ImportDocumentDetailCollectionDto,
    ImportDocumentDetailNextStep,
    ImportDocumentDetailRawRowDto,
    ImportDocumentDetailReadModel,
    ImportDocumentDetailValidationDto,
    ImportDocumentDetailValidationReasonCode,
    ImportDocumentDetailWorkflowDto,
    ImportDocumentSnapshot,
    ImportDocumentWorkflowStepState,
    ImportParseAttemptSnapshot,
    ImportRawTransactionRow,
)
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.documents.validation_report import (
    StoredValidationReport,
)
from app.features.imports.statements.types import RawTransactionStatus
from app.features.imports.statements.validation import (
    resolve_statement_validation_reason,
)

DETAIL_ROW_LIMIT = 5
DETAIL_ATTEMPT_LIMIT = 10


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
            account=snapshot.account,
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
    report: StoredValidationReport | None,
    *,
    rows: list[ImportRawTransactionRow],
) -> ImportDocumentDetailValidationDto | None:
    if report is None:
        return None
    return ImportDocumentDetailValidationDto(
        status=report.status,
        reason_code=_validation_reason_code(report),
        message=report.message,
        extracted_count=report.extracted_count,
        calculated_total_inflow=report.calculated_total_inflow,
        calculated_total_outflow=report.calculated_total_outflow,
        ignored_row_count=sum(row.status is RawTransactionStatus.IGNORED for row in rows),
        ignored_total_inflow=report.ignored_total_inflow,
        ignored_total_outflow=report.ignored_total_outflow,
        currency=report.currency,
        table_count=report.table_count,
        needs_mapping=report.needs_mapping,
    )


def _validation_reason_code(
    report: StoredValidationReport,
) -> ImportDocumentDetailValidationReasonCode:
    reason = ImportDocumentDetailValidationReasonCode
    if report.needs_mapping:
        return reason.NEEDS_MAPPING
    if report.status == "failed":
        return reason.VALIDATION_FAILED
    if report.statement_status is not None:
        return reason(
            resolve_statement_validation_reason(
                status=report.statement_status,
                balance_chain_status=report.balance_chain_status,
                unexplained_inflow_difference=report.unexplained_inflow_difference,
                unexplained_outflow_difference=report.unexplained_outflow_difference,
            ).value
        )
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
