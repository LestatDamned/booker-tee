from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.features.imports.application.documents.detail_reading import (
    DETAIL_ATTEMPT_LIMIT,
    DETAIL_ROW_LIMIT,
    ImportDocumentActionBlockingReason,
    ImportDocumentDetailNextStep,
    ImportDocumentDetailReader,
    ImportDocumentDetailValidationReasonCode,
    ImportDocumentWorkflowStepState,
)
from app.features.imports.application.documents.detail_view import (
    ImportDocumentDetailView,
    ImportParseAttemptView,
    ImportRawTransactionRow,
)
from app.features.imports.application.documents.management import (
    ImportDocumentManagementUseCase,
)
from app.features.imports.errors import ImportDocumentManagementError
from app.features.imports.models import (
    ParseAttemptStatus,
    RawTransactionStatus,
    UploadedDocumentStatus,
)


def test_document_detail_prioritizes_mapping_and_bounds_supporting_evidence() -> None:
    view = document_view(
        validation={
            "status": "needs_mapping",
            "message": "Configure columns.",
            "table_count": 3,
        },
        raw_transactions=[raw_row(index) for index in range(15)],
        parse_attempts=[parse_attempt(index) for index in range(12)],
    )

    detail = ImportDocumentDetailReader.from_view(view, can_manage=True)

    assert detail.next_step is ImportDocumentDetailNextStep.MAPPING
    assert detail.workflow.mapping is ImportDocumentWorkflowStepState.CURRENT
    assert detail.validation is not None
    assert detail.validation.table_count == 3
    assert detail.raw_rows.total == 15
    assert len(detail.raw_rows.items) == DETAIL_ROW_LIMIT
    assert detail.parse_attempts.total == 12
    assert len(detail.parse_attempts.items) == DETAIL_ATTEMPT_LIMIT


def test_document_detail_blocks_management_using_server_financial_facts() -> None:
    view = document_view(
        raw_transactions=[
            raw_row(
                1,
                status=RawTransactionStatus.CONFIRMED,
                linked_operation=True,
            )
        ]
    )

    detail = ImportDocumentDetailReader.from_view(view, can_manage=True)

    assert detail.next_step is ImportDocumentDetailNextStep.REVIEW
    assert detail.capabilities.ignore.allowed is False
    assert detail.capabilities.delete.allowed is False
    assert detail.capabilities.delete.blocking_reason_codes == (
        ImportDocumentActionBlockingReason.LINKED_OPERATIONS_EXIST,
    )


def test_document_detail_explains_mismatch_caused_by_ignored_rows() -> None:
    detail = ImportDocumentDetailReader.from_view(
        document_view(
            validation={
                "status": "mismatch",
                "message": "Итоги по строкам не совпадают с итогами выписки.",
                "extracted_count": 2,
                "calculated_total_inflow": "100.00",
                "calculated_total_outflow": "0.00",
                "ignored_total_inflow": "25.00",
                "ignored_total_outflow": "0.00",
                "unexplained_inflow_difference": "0.00",
                "unexplained_outflow_difference": "0.00",
                "currency": "RUB",
            },
            raw_transactions=[
                raw_row(1),
                raw_row(2, status=RawTransactionStatus.IGNORED),
            ],
        ),
        can_manage=True,
    )

    assert detail.validation is not None
    assert (
        detail.validation.reason_code
        is ImportDocumentDetailValidationReasonCode.IGNORED_ROWS_EXPLAIN_MISMATCH
    )
    assert detail.validation.ignored_row_count == 1
    assert detail.validation.ignored_total_inflow == "25.00"


def test_document_detail_viewer_gets_same_status_truth_without_mutations() -> None:
    detail = ImportDocumentDetailReader.from_view(
        document_view(status=UploadedDocumentStatus.FAILED_TO_PARSE),
        can_manage=False,
    )

    assert detail.status is UploadedDocumentStatus.FAILED_TO_PARSE
    assert detail.workflow.extract is ImportDocumentWorkflowStepState.BLOCKED
    assert detail.next_step is ImportDocumentDetailNextStep.DOCUMENT_LIST
    assert detail.capabilities.can_manage is False
    assert detail.capabilities.ignore.blocking_reason_codes == (
        ImportDocumentActionBlockingReason.IMPORT_MANAGEMENT_FORBIDDEN,
    )


@pytest.mark.asyncio
async def test_document_management_rejects_stale_expected_status_before_mutation() -> None:
    class ImportsStub:
        async def get_document_for_workspace_for_update(
            self,
            workspace_id,
            document_id,
        ):
            return type(
                "DocumentStub",
                (),
                {
                    "status": UploadedDocumentStatus.PARSED,
                    "raw_transactions": [],
                },
            )()

    use_case = object.__new__(ImportDocumentManagementUseCase)
    use_case.imports = ImportsStub()

    with pytest.raises(
        ImportDocumentManagementError,
        match="Состояние документа изменилось",
    ):
        await use_case.ignore_document(
            workspace_id=uuid4(),
            document_id=uuid4(),
            expected_status=UploadedDocumentStatus.REQUIRES_REVIEW,
        )


def document_view(
    *,
    status: UploadedDocumentStatus = UploadedDocumentStatus.REQUIRES_REVIEW,
    validation: dict[str, object] | None = None,
    raw_transactions: list[ImportRawTransactionRow] | None = None,
    parse_attempts: list[ImportParseAttemptView] | None = None,
) -> ImportDocumentDetailView:
    return ImportDocumentDetailView(
        id=uuid4(),
        status=status,
        original_filename="statement.pdf",
        sha256_hash="a" * 64,
        storage_key="private/storage.pdf",
        bank_name="Альфа-Банк",
        statement_type="account_statement",
        account=None,
        validation=validation,
        raw_transactions=raw_transactions or [],
        parse_attempts=parse_attempts or [],
        statement_period_start=date(2026, 7, 1),
        statement_period_end=date(2026, 7, 31),
        file_size_bytes=2048,
        created_at=datetime(2026, 7, 24, 10, tzinfo=UTC),
        updated_at=datetime(2026, 7, 24, 10, tzinfo=UTC),
    )


def raw_row(
    index: int,
    *,
    status: RawTransactionStatus = RawTransactionStatus.NORMALIZED,
    linked_operation: bool = False,
) -> ImportRawTransactionRow:
    return ImportRawTransactionRow(
        row_index=index,
        status=status,
        parse_attempt_id=uuid4(),
        display_date=date(2026, 7, 1),
        amount=Decimal("-100.00"),
        amount_raw="-100.00",
        currency="RUB",
        description=f"Операция {index}",
        normalization_error="",
        linked_operation_id=uuid4() if linked_operation else None,
    )


def parse_attempt(index: int) -> ImportParseAttemptView:
    return ImportParseAttemptView(
        id=uuid4(),
        status=ParseAttemptStatus.SUCCESS,
        parser_name=f"parser_{index}",
        parser_version="1",
        started_at=datetime(2026, 7, 24, 10, tzinfo=UTC),
        finished_at=datetime(2026, 7, 24, 10, 1, tzinfo=UTC),
        error_message=None,
        validation_report=None,
        raw_tables=None,
        raw_text_by_page=None,
    )
