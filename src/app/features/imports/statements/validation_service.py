"""Calculation and persistence of imported document validation."""

from dataclasses import dataclass

from app.features.imports.documents.attempts import (
    latest_parse_attempt,
    statement_control_totals_from_json,
)
from app.features.imports.documents.lifecycle import transition_document_status
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.documents.types import ParseAttemptStatus, UploadedDocumentStatus
from app.features.imports.models import (
    ParseAttempt,
    UploadedDocument,
)
from app.features.imports.statements.dto import StatementControlTotals
from app.features.imports.statements.validation import (
    StatementValidationReport,
    StatementValidationStatus,
    validate_statement_totals,
)


@dataclass(frozen=True)
class CalculatedDocumentValidation:
    attempt: ParseAttempt
    control_totals: StatementControlTotals | None
    report: StatementValidationReport


class StatementValidationService:
    def __init__(self, documents: DocumentRepository) -> None:
        self._documents = documents

    @staticmethod
    def calculate_for_document(
        document: UploadedDocument,
    ) -> CalculatedDocumentValidation | None:
        attempt = latest_parse_attempt(document)
        if attempt is None:
            return None
        control_totals = statement_control_totals_from_json(attempt.control_totals_json)
        return CalculatedDocumentValidation(
            attempt=attempt,
            control_totals=control_totals,
            report=validate_statement_totals(
                rows=document.raw_transactions,
                control_totals=control_totals,
            ),
        )

    async def store_result(
        self,
        document: UploadedDocument,
        attempt: ParseAttempt,
        *,
        control_totals: StatementControlTotals | None,
        report: StatementValidationReport,
    ) -> None:
        await self._documents.store_attempt_validation(
            attempt,
            control_totals=control_totals.as_json() if control_totals else None,
            validation_report=report.as_json(),
        )
        if report.status == StatementValidationStatus.VALID:
            await self._documents.mark_attempt_status(attempt, ParseAttemptStatus.SUCCESS)
            await transition_document_status(
                self._documents,
                document,
                UploadedDocumentStatus.PARSED,
            )
            return

        await self._documents.mark_attempt_status(attempt, ParseAttemptStatus.REQUIRES_REVIEW)
        await transition_document_status(
            self._documents,
            document,
            UploadedDocumentStatus.REQUIRES_REVIEW,
        )

    async def refresh_for_document(self, document: UploadedDocument) -> None:
        validation = self.calculate_for_document(document)
        if validation is None:
            return
        await self.store_result(
            document,
            validation.attempt,
            control_totals=validation.control_totals,
            report=validation.report,
        )
