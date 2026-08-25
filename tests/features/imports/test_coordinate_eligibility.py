from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.features.imports.documents.types import (
    UploadedDocumentSource,
    UploadedDocumentStatus,
    UploadedDocumentType,
)
from app.features.imports.mapping.coordinate_dto import (
    CoordinateFieldRole,
    CoordinateMappingSpec,
    CoordinatePageLayout,
    NormalizedRect,
)
from app.features.imports.mapping.coordinate_engine import CoordinateWord
from app.features.imports.mapping.coordinate_service import (
    CoordinateMappingImportService,
    CoordinateMappingService,
    _document_reasons,
)
from app.features.imports.mapping.errors import MappingImportUnavailableError


def test_coordinate_mapping_requires_server_owned_needs_mapping_report() -> None:
    document = _document({"status": "valid"})
    assert "mapping_not_required" in _document_reasons(document)


def test_coordinate_mapping_rejects_invalid_lifecycle_status() -> None:
    document = _document({"status": "needs_mapping"})
    document.status = UploadedDocumentStatus.IMPORTED
    assert "status_not_eligible" in _document_reasons(document)


def test_coordinate_mapping_allows_unknown_statement_review() -> None:
    assert _document_reasons(_document({"status": "needs_mapping"})) == []


def test_coordinate_mapping_allows_unconfirmed_visual_remap() -> None:
    assert (
        _document_reasons(_document({"status": "valid", "source": "visual_coordinate_mapping"}))
        == []
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("report", "status"),
    [
        ({"status": "valid"}, UploadedDocumentStatus.REQUIRES_REVIEW),
        ({"status": "needs_mapping"}, UploadedDocumentStatus.IMPORTED),
    ],
)
async def test_import_rechecks_eligibility_under_lock_without_mutation(report, status) -> None:
    document = _document(report)
    document.id = uuid4()
    document.status = status
    documents = SimpleNamespace(
        get_document_for_workspace_for_update=_async_result(document),
    )
    templates = SimpleNamespace(get_mapping_execution=_async_result(None))
    session = SimpleNamespace(commit=_unexpected_async_call)
    service = object.__new__(CoordinateMappingImportService)
    service._documents = documents
    service._templates = templates
    service._session = session

    with pytest.raises(MappingImportUnavailableError):
        await service.import_rows_idempotently(
            workspace_id=uuid4(),
            document_id=document.id,
            spec=_spec(),
            idempotency_key=uuid4(),
            template_name=None,
        )


@pytest.mark.asyncio
async def test_preview_is_bounded_and_has_no_persistence_side_effects() -> None:
    document = _document({"status": "needs_mapping"})
    document.id = uuid4()
    document.original_filename = "statement.pdf"
    service = object.__new__(CoordinateMappingService)
    service._documents = SimpleNamespace(get_document_for_workspace=_async_result(document))

    async def words(_document, _spec):
        values = []
        for index in range(25):
            top = 120 + index * 30
            values.extend(
                [
                    CoordinateWord("01.08.2026", 50, 130, top, top + 10),
                    CoordinateWord(f"Row {index}", 250, 350, top, top + 10),
                    CoordinateWord("-1", 750, 850, top, top + 10),
                ]
            )
        return [(1000, 1000, values)]

    service._validated_words = words
    preview = await service.preview(workspace_id=uuid4(), document_id=document.id, spec=_spec())

    assert preview is not None
    assert preview.total_row_count == 25
    assert len(preview.rows) == 20
    assert preview.rows_truncated is True


def _async_result(value):
    async def call(*_args, **_kwargs):
        return value

    return call


async def _unexpected_async_call(*_args, **_kwargs):
    raise AssertionError("ineligible import mutated persistence")


def _spec() -> CoordinateMappingSpec:
    row = NormalizedRect(x0=0.05, y0=0.2, x1=0.95, y1=0.3)
    return CoordinateMappingSpec(
        default_currency="RUB",
        layouts={
            "first": CoordinatePageLayout(
                page_aspect_ratio=0.75,
                transaction_top=0.1,
                transaction_bottom=0.9,
                sample_row=row,
                fields={
                    CoordinateFieldRole.OPERATION_DATE: NormalizedRect(
                        x0=0.05, y0=0.2, x1=0.2, y1=0.3
                    ),
                    CoordinateFieldRole.DESCRIPTION: NormalizedRect(
                        x0=0.25, y0=0.2, x1=0.65, y1=0.3
                    ),
                    CoordinateFieldRole.AMOUNT: NormalizedRect(x0=0.75, y0=0.2, x1=0.95, y1=0.3),
                },
            )
        },
    )


def _document(validation_report):
    return SimpleNamespace(
        content_type="application/pdf",
        document_type=UploadedDocumentType.BANK_STATEMENT,
        source=UploadedDocumentSource.WEB_UPLOAD,
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        storage_key="workspace/statement.pdf",
        account_id=object(),
        raw_transactions=[],
        parse_attempts=[
            SimpleNamespace(
                started_at=datetime.now(UTC),
                validation_report_json=validation_report,
            )
        ],
    )
