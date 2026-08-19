from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from stat import S_IMODE
from threading import get_ident
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi import UploadFile
from openpyxl import Workbook

from app.features.import_review.domain.queue import REVIEW_QUEUE_STATUSES
from app.features.import_review.repository import ImportReviewRepository
from app.features.imports.documents.attempts import record_failed_parse_attempt
from app.features.imports.documents.commands.upload import (
    StatementUploadUseCase,
    extract_statement,
    validate_statement_upload,
)
from app.features.imports.documents.errors import (
    UploadIdempotencyConflictError,
    UploadTooLargeError,
    UploadValidationError,
)
from app.features.imports.documents.storage import (
    UploadStorage,
    sanitize_upload_filename,
)
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.models import ParseAttempt, RawTransaction, UploadedDocument
from app.features.imports.parsers.extractors import pdf as pdf_extractor_module
from app.features.imports.parsers.extractors.dto import (
    ExtractedStatement,
    ExtractedStatementPageTables,
)
from app.features.imports.parsers.extractors.limits import (
    StatementExtractionLimits,
    StatementResourceLimitError,
)
from app.features.imports.parsers.extractors.pdf import (
    PdfPlumberStatementExtractor,
)
from app.features.imports.parsers.extractors.resolver import (
    StatementExtractor,
    StatementExtractorResolver,
)
from app.features.imports.parsers.extractors.xlsx import (
    OpenPyxlStatementExtractor,
)
from app.features.imports.parsers.support.normalization import (
    parse_bank_date,
)
from app.features.imports.statements.deduplication import possible_duplicate_fingerprint
from app.features.imports.statements.process import StatementParseCompletionService
from app.features.imports.statements.types import RawTransactionStatus


def test_sanitize_upload_filename_removes_paths_and_unsafe_characters() -> None:
    assert sanitize_upload_filename("../bank statement июнь.pdf") == "bank_statement_.pdf"
    assert sanitize_upload_filename("statement") == "statement"
    assert sanitize_upload_filename("../bank statement июнь.xlsx") == "bank_statement_.xlsx"


@pytest.mark.asyncio
async def test_upload_storage_preserves_pdf_bytes(tmp_path: Path) -> None:
    content = b"%PDF-1.4 local fixture bytes"
    upload = UploadFile(file=BytesIO(content), filename="../private-bank-statement.pdf")
    workspace_id = uuid4()
    document_id = uuid4()

    stored = await UploadStorage(tmp_path).save_upload(
        upload,
        workspace_id=workspace_id,
        document_id=document_id,
    )

    assert stored.file_size_bytes == len(content)
    assert stored.sha256_hash == sha256(content).hexdigest()
    assert stored.path.read_bytes() == content
    assert stored.storage_key == f"{workspace_id}/{document_id}/source.pdf"
    assert "private-bank-statement" not in stored.storage_key
    assert S_IMODE(stored.path.stat().st_mode) == 0o600
    assert S_IMODE(tmp_path.stat().st_mode) == 0o700  # noqa: ASYNC240
    assert S_IMODE(stored.path.parent.stat().st_mode) == 0o700
    assert S_IMODE(stored.path.parent.parent.stat().st_mode) == 0o700


@pytest.mark.asyncio
async def test_upload_storage_preserves_xlsx_extension(tmp_path: Path) -> None:
    workbook_file = BytesIO()
    workbook = Workbook()
    workbook.active["A1"] = "Дата"
    workbook.save(workbook_file)
    workbook.close()
    content = workbook_file.getvalue()
    upload = UploadFile(file=BytesIO(content), filename="../statement.xlsx")
    workspace_id = uuid4()
    document_id = uuid4()

    stored = await UploadStorage(tmp_path).save_upload(
        upload,
        workspace_id=workspace_id,
        document_id=document_id,
    )

    assert stored.file_size_bytes == len(content)
    assert stored.sha256_hash == sha256(content).hexdigest()
    assert stored.path.read_bytes() == content
    assert stored.storage_key == f"{workspace_id}/{document_id}/source.xlsx"


@pytest.mark.asyncio
async def test_upload_storage_rejects_oversized_file_without_leaving_partial(
    tmp_path: Path,
) -> None:
    upload = UploadFile(file=BytesIO(b"too large"), filename="statement.pdf")

    with pytest.raises(UploadTooLargeError):
        await UploadStorage(tmp_path).save_upload(
            upload,
            workspace_id=uuid4(),
            document_id=uuid4(),
            max_bytes=4,
        )

    assert list(tmp_path.rglob("source.pdf")) == []  # noqa: ASYNC240


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("statement.pdf", b"not a PDF", "PDF"),
        ("statement.xlsx", b"not an XLSX", "XLSX"),
    ],
)
async def test_upload_storage_rejects_invalid_file_signature(
    tmp_path: Path,
    filename: str,
    content: bytes,
    message: str,
) -> None:
    with pytest.raises(UploadValidationError, match=message):
        await UploadStorage(tmp_path).save_upload(
            UploadFile(file=BytesIO(content), filename=filename),
            workspace_id=uuid4(),
            document_id=uuid4(),
        )

    assert list(tmp_path.rglob("source.*")) == []  # noqa: ASYNC240


@pytest.mark.asyncio
async def test_upload_storage_rejects_zip_without_xlsx_structure(tmp_path: Path) -> None:
    content = BytesIO()
    with ZipFile(content, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("unrelated.txt", "not a workbook")

    with pytest.raises(UploadValidationError, match="XLSX"):
        await UploadStorage(tmp_path).save_upload(
            UploadFile(file=BytesIO(content.getvalue()), filename="statement.xlsx"),
            workspace_id=uuid4(),
            document_id=uuid4(),
        )

    assert list(tmp_path.rglob("source.xlsx")) == []  # noqa: ASYNC240


@pytest.mark.asyncio
async def test_upload_storage_does_not_overwrite_existing_file(tmp_path: Path) -> None:
    storage = UploadStorage(tmp_path)
    workspace_id = uuid4()
    document_id = uuid4()
    original = b"%PDF-1.4 original"
    stored = await storage.save_upload(
        UploadFile(file=BytesIO(original), filename="first.pdf"),
        workspace_id=workspace_id,
        document_id=document_id,
    )

    with pytest.raises(UploadValidationError, match="уже существует"):
        await storage.save_upload(
            UploadFile(file=BytesIO(b"%PDF-1.4 replacement"), filename="second.pdf"),
            workspace_id=workspace_id,
            document_id=document_id,
        )

    assert stored.path.read_bytes() == original


@pytest.mark.asyncio
async def test_upload_storage_rejects_path_through_symlink(tmp_path: Path) -> None:
    root_dir = tmp_path / "uploads"
    outside_dir = tmp_path / "outside"
    root_dir.mkdir()
    outside_dir.mkdir()
    workspace_id = uuid4()
    (root_dir / str(workspace_id)).symlink_to(outside_dir, target_is_directory=True)

    with pytest.raises(UploadValidationError, match="storage path"):
        await UploadStorage(root_dir).save_upload(
            UploadFile(file=BytesIO(b"%PDF-1.4"), filename="statement.pdf"),
            workspace_id=workspace_id,
            document_id=uuid4(),
        )

    assert list(outside_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_statement_upload_replays_same_idempotent_payload(tmp_path: Path) -> None:
    workspace_id = uuid4()
    account = SimpleNamespace(id=uuid4(), currency="RUB")
    content = b"%PDF-1.4 replay"
    existing = SimpleNamespace(
        id=uuid4(),
        account_id=account.id,
        original_filename="statement.pdf",
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        sha256_hash=sha256(content).hexdigest(),
    )

    class Accounts:
        async def get_import_account(self, requested_workspace_id, account_id):
            assert requested_workspace_id == workspace_id
            assert account_id == account.id
            return account

    class Imports:
        async def get_document_for_workspace(self, requested_workspace_id, _document_id):
            assert requested_workspace_id == workspace_id
            return existing

    use_case = object.__new__(StatementUploadUseCase)
    use_case.settings = SimpleNamespace(statement_upload_max_bytes=1024)
    use_case.accounts = Accounts()
    use_case.documents = Imports()
    use_case.storage = UploadStorage(tmp_path)

    result = await use_case.upload_statement(
        context=cast(
            Any,
            SimpleNamespace(
                workspace=SimpleNamespace(id=workspace_id),
                user=SimpleNamespace(id=uuid4()),
            ),
        ),
        upload_file=UploadFile(file=BytesIO(content), filename="statement.pdf"),
        account_id=account.id,
        idempotency_key=uuid4(),
    )

    assert result.replayed is True
    assert result.document_id == existing.id
    assert result.document_status is existing.status
    assert result.filename == existing.original_filename
    assert list(tmp_path.rglob("source.pdf")) == []  # noqa: ASYNC240


@pytest.mark.asyncio
async def test_statement_upload_rejects_changed_idempotent_payload(tmp_path: Path) -> None:
    workspace_id = uuid4()
    account = SimpleNamespace(id=uuid4(), currency="RUB")
    existing = SimpleNamespace(
        account_id=account.id,
        original_filename="statement.pdf",
        sha256_hash=sha256(b"first").hexdigest(),
    )

    class Accounts:
        async def get_import_account(self, *_args):
            return account

    class Imports:
        async def get_document_for_workspace(self, *_args):
            return existing

    use_case = object.__new__(StatementUploadUseCase)
    use_case.settings = SimpleNamespace(statement_upload_max_bytes=1024)
    use_case.accounts = Accounts()
    use_case.documents = Imports()
    use_case.storage = UploadStorage(tmp_path)

    with pytest.raises(UploadIdempotencyConflictError):
        await use_case.upload_statement(
            context=cast(
                Any,
                SimpleNamespace(
                    workspace=SimpleNamespace(id=workspace_id),
                    user=SimpleNamespace(id=uuid4()),
                ),
            ),
            upload_file=UploadFile(file=BytesIO(b"second"), filename="statement.pdf"),
            account_id=account.id,
            idempotency_key=uuid4(),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("activity_fails", [False, True])
async def test_statement_upload_cleans_stored_file_when_first_transaction_fails(
    tmp_path: Path,
    activity_fails: bool,
) -> None:
    workspace_id = uuid4()
    account = SimpleNamespace(id=uuid4(), currency="RUB")

    class Session:
        def __init__(self) -> None:
            self.commits = 0
            self.rollbacks = 0

        async def commit(self) -> None:
            self.commits += 1

        async def rollback(self) -> None:
            self.rollbacks += 1

    class Accounts:
        async def get_import_account(self, *_args: object) -> object:
            return account

    class Documents:
        async def create_uploaded_document(self, document: object) -> object:
            if not activity_fails:
                raise RuntimeError("document write failed")
            return document

    class UploadStub:
        filename = "../statement.pdf"
        content_type = "application/pdf"

        def __init__(self) -> None:
            self.file = BytesIO(b"%PDF-1.4")

        async def read(self, size: int = -1) -> bytes:
            return self.file.read(size)

        async def seek(self, offset: int) -> None:
            self.file.seek(offset)

    session = Session()
    use_case = object.__new__(StatementUploadUseCase)
    use_case.session = cast(Any, session)
    use_case.settings = cast(
        Any,
        SimpleNamespace(
            statement_upload_max_bytes=1024,
            upload_storage_dir=tmp_path,
        ),
    )
    use_case.accounts = cast(Any, Accounts())
    use_case.documents = cast(Any, Documents())
    use_case.storage = UploadStorage(tmp_path)
    activity = AsyncMock(side_effect=RuntimeError("activity failed"))
    use_case.activity = cast(Any, SimpleNamespace(document_uploaded=activity))

    with pytest.raises(RuntimeError, match="activity failed|document write failed"):
        await use_case.upload_statement(
            context=cast(
                Any,
                SimpleNamespace(
                    workspace=SimpleNamespace(id=workspace_id),
                    user=SimpleNamespace(id=uuid4()),
                ),
            ),
            upload_file=cast(UploadFile, UploadStub()),
            account_id=account.id,
        )

    assert session.commits == 0
    assert session.rollbacks == 1
    assert activity.await_count == (1 if activity_fails else 0)
    if activity_fails:
        assert activity.await_args is not None
        assert activity.await_args.kwargs["details"].display_filename == "statement.pdf"
    assert list(tmp_path.rglob("source.pdf")) == []  # noqa: ASYNC240


def test_validate_statement_upload_accepts_pdf_and_xlsx() -> None:
    validate_statement_upload(UploadFile(file=BytesIO(b"%PDF-1.4"), filename="statement.pdf"))
    validate_statement_upload(UploadFile(file=BytesIO(b"xlsx"), filename="statement.xlsx"))


def test_validate_statement_upload_rejects_unknown_extension() -> None:
    upload = UploadFile(file=BytesIO(b"not a pdf"), filename="statement.txt")

    with pytest.raises(UploadValidationError):
        validate_statement_upload(upload)


@pytest.mark.asyncio
async def test_statement_extraction_runs_outside_event_loop() -> None:
    event_loop_thread = get_ident()
    extraction_thread: int | None = None
    extracted = ExtractedStatement(
        text_by_page=[],
        tables_by_page=[],
        metadata={},
    )

    class Extractor:
        def extract(self, _file_path: Path) -> ExtractedStatement:
            nonlocal extraction_thread
            extraction_thread = get_ident()
            return extracted

    result = await extract_statement(
        cast(StatementExtractor, Extractor()),
        Path("statement.pdf"),
    )

    assert result is extracted
    assert extraction_thread is not None
    assert extraction_thread != event_loop_thread


@pytest.mark.asyncio
async def test_inactive_workspace_preserves_extracted_import_without_mapping_rows() -> None:
    document = SimpleNamespace(status=UploadedDocumentStatus.PARSING)
    attempt = SimpleNamespace(finished_at=None)

    class Documents:
        def __init__(self) -> None:
            self.raw_payload = None
            self.review_message = None

        async def mark_attempt_success(self, _attempt, **values):
            self.raw_payload = values

        async def mark_attempt_requires_review(self, _attempt, *, message, **_kwargs):
            self.review_message = message

        async def mark_document_status(self, target, status):
            target.status = status

    documents = Documents()
    service = StatementParseCompletionService(
        session=cast(Any, object()),
        documents=cast(Any, documents),
        statements=cast(Any, object()),
        mappings=cast(Any, object()),
        parser_registry=cast(Any, object()),
    )
    extracted = ExtractedStatement(
        text_by_page=["raw financial text"],
        tables_by_page=[
            ExtractedStatementPageTables(
                page_number=1,
                tables=[[["Дата", "Сумма"], ["2026-08-04", "-10.00"]]],
            )
        ],
        metadata={"source_format": "pdf"},
    )

    await service.preserve_inactive_workspace_attempt(
        cast(UploadedDocument, document),
        cast(ParseAttempt, attempt),
        extracted,
    )

    assert attempt.finished_at is not None
    assert documents.raw_payload == {
        "raw_text_by_page_json": ["raw financial text"],
        "raw_tables_json": [
            {"page_number": 1, "tables": [[["Дата", "Сумма"], ["2026-08-04", "-10.00"]]]}
        ],
        "metadata": {"source_format": "pdf"},
    }
    assert document.status == UploadedDocumentStatus.REQUIRES_REVIEW
    assert documents.review_message is not None
    assert "deactivated during parsing" in documents.review_message


def test_pdfplumber_extractor_preserves_raw_pages() -> None:
    extracted = PdfPlumberStatementExtractor().extract(
        Path("tests/fixtures/expobank_statement.pdf")
    )

    assert extracted.text_by_page
    assert len(extracted.tables_by_page) == len(extracted.text_by_page)
    assert all(page.page_number >= 1 for page in extracted.tables_by_page)


def test_pdf_extractor_rejects_document_over_page_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class PdfStub:
        metadata: dict[str, object] = {}
        pages = [object(), object()]

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(pdf_extractor_module.pdfplumber, "open", lambda _path: PdfStub())

    with pytest.raises(StatementResourceLimitError, match="1-page"):
        PdfPlumberStatementExtractor(StatementExtractionLimits(pdf_max_pages=1)).extract(
            Path("oversized.pdf")
        )


def test_openpyxl_extractor_preserves_sheet_tables(tmp_path: Path) -> None:
    workbook_path = tmp_path / "statement.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Card"
    sheet.append(["Дата", "Описание", "Сумма"])
    sheet.append(["2026-06-01", "Coffee", -10.5])
    sheet.append([None, None, None])
    workbook.save(workbook_path)

    extracted = OpenPyxlStatementExtractor().extract(workbook_path)

    assert extracted.metadata["source_format"] == "xlsx"
    assert extracted.metadata["sheet_names"] == ["Card"]
    assert extracted.text_by_page == ["Дата\tОписание\tСумма\n2026-06-01\tCoffee\t-10.5"]
    assert extracted.tables_by_page[0].page_number == 1
    assert extracted.tables_by_page[0].tables == [
        [
            ["Дата", "Описание", "Сумма"],
            ["2026-06-01", "Coffee", "-10.5"],
        ]
    ]


def test_xlsx_extractor_rejects_large_uncompressed_archive(tmp_path: Path) -> None:
    workbook_path = tmp_path / "oversized.xlsx"
    with ZipFile(workbook_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", "x" * 101)

    with pytest.raises(StatementResourceLimitError, match="uncompressed size"):
        OpenPyxlStatementExtractor(
            StatementExtractionLimits(xlsx_max_uncompressed_bytes=100)
        ).extract(workbook_path)


@pytest.mark.parametrize(
    ("limits", "cell", "message"),
    [
        (StatementExtractionLimits(xlsx_max_rows_per_sheet=1), "A2", "row"),
        (StatementExtractionLimits(xlsx_max_columns_per_sheet=1), "B1", "column"),
        (StatementExtractionLimits(xlsx_max_cells=3), "B2", "total cell"),
    ],
)
def test_xlsx_extractor_enforces_sheet_dimensions(
    tmp_path: Path,
    limits: StatementExtractionLimits,
    cell: str,
    message: str,
) -> None:
    workbook_path = tmp_path / "oversized.xlsx"
    workbook = Workbook()
    workbook.active[cell] = "value"
    workbook.save(workbook_path)

    with pytest.raises(StatementResourceLimitError, match=message):
        OpenPyxlStatementExtractor(limits).extract(workbook_path)


def test_xlsx_extractor_enforces_sheet_count(tmp_path: Path) -> None:
    workbook_path = tmp_path / "oversized.xlsx"
    workbook = Workbook()
    workbook.create_sheet("Second")
    workbook.save(workbook_path)

    with pytest.raises(StatementResourceLimitError, match="1-sheet"):
        OpenPyxlStatementExtractor(StatementExtractionLimits(xlsx_max_sheets=1)).extract(
            workbook_path
        )


@pytest.mark.asyncio
async def test_resource_limit_failure_preserves_document_and_failed_attempt() -> None:
    document = SimpleNamespace(status=UploadedDocumentStatus.PARSING)
    attempt = SimpleNamespace(finished_at=None)

    class Documents:
        def __init__(self) -> None:
            self.error_code: str | None = None
            self.error_message: str | None = None

        async def mark_attempt_failed(
            self,
            _attempt: object,
            *,
            error_code: str,
            error_message: str,
        ) -> None:
            self.error_code = error_code
            self.error_message = error_message

        async def mark_document_status(
            self,
            target: Any,
            status: UploadedDocumentStatus,
        ) -> None:
            target.status = status

    documents = Documents()
    await record_failed_parse_attempt(
        cast(Any, documents),
        cast(UploadedDocument, document),
        cast(ParseAttempt, attempt),
        StatementResourceLimitError("XLSX exceeds configured limits."),
    )

    assert attempt.finished_at is not None
    assert documents.error_code == "StatementResourceLimitError"
    assert documents.error_message == (
        "StatementResourceLimitError: XLSX exceeds configured limits."
    )
    assert document.status is UploadedDocumentStatus.FAILED_TO_PARSE


def test_statement_extractor_resolver_selects_extractor_by_extension(tmp_path: Path) -> None:
    workbook_path = tmp_path / "statement.xlsx"
    workbook = Workbook()
    workbook.active.append(["Date", "Amount"])
    workbook.save(workbook_path)

    extracted = StatementExtractorResolver().extract(workbook_path)

    assert extracted.metadata["source_format"] == "xlsx"


def test_reviewable_raw_transaction_statuses_include_normalized_rows() -> None:
    assert RawTransactionStatus.NORMALIZED in REVIEW_QUEUE_STATUSES
    assert RawTransactionStatus.SUGGESTED in REVIEW_QUEUE_STATUSES
    assert RawTransactionStatus.MATCHED in REVIEW_QUEUE_STATUSES
    assert RawTransactionStatus.CONFIRMED not in REVIEW_QUEUE_STATUSES
    assert RawTransactionStatus.IGNORED not in REVIEW_QUEUE_STATUSES
    assert RawTransactionStatus.DUPLICATE not in REVIEW_QUEUE_STATUSES


@pytest.mark.asyncio
async def test_duplicate_candidate_query_is_workspace_and_document_scoped() -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    account_id = uuid4()

    class ResultStub:
        def scalars(self) -> Any:
            return self

        def all(self) -> list[object]:
            return []

    class SessionStub:
        statement: object | None = None

        async def execute(self, statement: object) -> ResultStub:
            self.statement = statement
            return ResultStub()

    session = SessionStub()
    await ImportReviewRepository(cast(Any, session)).list_possible_duplicate_candidates(
        workspace_id=workspace_id,
        fingerprints={(account_id, date(2026, 7, 20), Decimal("-1250.50"), "RUB")},
        exclude_document_id=document_id,
    )

    assert session.statement is not None
    compiled = cast(Any, session.statement).compile()
    assert workspace_id in compiled.params.values()
    assert document_id in compiled.params.values()
    assert "raw_transactions.workspace_id" in str(compiled)
    assert "raw_transactions.uploaded_document_id !=" in str(compiled)


def test_possible_duplicate_fingerprint_requires_normalized_fields() -> None:
    account_id = uuid4()
    raw_transaction = raw_transaction_from_values(
        account_id=account_id,
        amount=Decimal("10.00"),
    )

    assert possible_duplicate_fingerprint(raw_transaction) == (
        account_id,
        parse_bank_date("29.05.2026"),
        Decimal("10.00"),
        "RUB",
    )
    raw_transaction.amount = None
    assert possible_duplicate_fingerprint(raw_transaction) is None


def raw_transaction_from_values(
    *,
    account_id: UUID | None = None,
    amount: Decimal | None = Decimal("10.00"),
) -> RawTransaction:
    return RawTransaction(
        workspace_id=uuid4(),
        uploaded_document_id=uuid4(),
        parse_attempt_id=uuid4(),
        row_index=0,
        status=RawTransactionStatus.NORMALIZED,
        raw_payload={},
        account_id=account_id,
        operation_date=parse_bank_date("29.05.2026"),
        amount=amount,
        currency="RUB",
        normalization_error=None,
    )
