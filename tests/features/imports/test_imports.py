from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile
from openpyxl import Workbook

from app.features.imports.application.documents.management import document_has_linked_operations
from app.features.imports.application.documents.upload import validate_statement_upload
from app.features.imports.application.review.status import (
    RawTransactionReviewStatusUseCase,
    raw_transaction_status_for_review_action,
)
from app.features.imports.domain.deduplication import (
    mark_raw_transaction_duplicate,
    possible_duplicate_fingerprint,
)
from app.features.imports.errors import UploadValidationError
from app.features.imports.infrastructure.extraction.openpyxl_extractor import (
    OpenPyxlStatementExtractor,
)
from app.features.imports.infrastructure.extraction.pdfplumber_extractor import (
    PdfPlumberExtractor,
)
from app.features.imports.infrastructure.extraction.resolver import StatementExtractorResolver
from app.features.imports.infrastructure.storage import (
    UploadStorage,
    sanitize_filename,
    sanitize_upload_filename,
)
from app.features.imports.models import RawTransaction, RawTransactionStatus, UploadedDocumentStatus
from app.features.imports.parsing.support.normalization import (
    parse_bank_date,
)
from app.features.imports.presentation.review.item import review_row_anchor
from app.features.imports.presentation.review.page import (
    build_review_page_context,
    review_redirect_url,
)
from app.features.imports.query_repository import REVIEWABLE_RAW_TRANSACTION_STATUSES
from app.features.ledger.models import OperationType


def test_sanitize_filename_removes_paths_and_unsafe_characters() -> None:
    assert sanitize_filename("../bank statement июнь.pdf") == "bank_statement_.pdf"
    assert sanitize_filename("statement") == "statement.pdf"
    assert sanitize_upload_filename("../bank statement июнь.xlsx") == "bank_statement_.xlsx"


@pytest.mark.asyncio
async def test_upload_storage_preserves_pdf_bytes(tmp_path: Path) -> None:
    content = b"%PDF-1.4 local fixture bytes"
    upload = UploadFile(file=BytesIO(content), filename="../statement.pdf")
    workspace_id = uuid4()
    document_id = uuid4()

    stored = await UploadStorage(tmp_path).save_pdf(
        upload,
        workspace_id=workspace_id,
        document_id=document_id,
    )

    assert stored.file_size_bytes == len(content)
    assert stored.sha256_hash == sha256(content).hexdigest()
    assert stored.path.read_bytes() == content
    assert stored.storage_key == f"{workspace_id}/{document_id}/statement.pdf"


@pytest.mark.asyncio
async def test_upload_storage_save_pdf_keeps_legacy_pdf_suffix(tmp_path: Path) -> None:
    upload = UploadFile(file=BytesIO(b"%PDF-1.4"), filename="statement")
    workspace_id = uuid4()
    document_id = uuid4()

    stored = await UploadStorage(tmp_path).save_pdf(
        upload,
        workspace_id=workspace_id,
        document_id=document_id,
    )

    assert stored.storage_key == f"{workspace_id}/{document_id}/statement.pdf"


@pytest.mark.asyncio
async def test_upload_storage_preserves_xlsx_extension(tmp_path: Path) -> None:
    content = b"local xlsx fixture bytes"
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
    assert stored.storage_key == f"{workspace_id}/{document_id}/statement.xlsx"


def test_validate_statement_upload_accepts_pdf_and_xlsx() -> None:
    validate_statement_upload(UploadFile(file=BytesIO(b"%PDF-1.4"), filename="statement.pdf"))
    validate_statement_upload(UploadFile(file=BytesIO(b"xlsx"), filename="statement.xlsx"))


def test_validate_statement_upload_rejects_unknown_extension() -> None:
    upload = UploadFile(file=BytesIO(b"not a pdf"), filename="statement.txt")

    with pytest.raises(UploadValidationError):
        validate_statement_upload(upload)


def test_pdfplumber_extractor_preserves_raw_pages() -> None:
    extracted = PdfPlumberExtractor().extract(Path("tests/fixtures/expobank_statement.pdf"))

    assert extracted.text_by_page
    assert len(extracted.tables_by_page) == len(extracted.text_by_page)
    assert all(page.page_number >= 1 for page in extracted.tables_by_page)


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


def test_statement_extractor_resolver_selects_extractor_by_extension(tmp_path: Path) -> None:
    workbook_path = tmp_path / "statement.xlsx"
    workbook = Workbook()
    workbook.active.append(["Date", "Amount"])
    workbook.save(workbook_path)

    extracted = StatementExtractorResolver().extract(workbook_path)

    assert extracted.metadata["source_format"] == "xlsx"


def test_raw_transaction_review_actions_map_to_statuses() -> None:
    assert raw_transaction_status_for_review_action("duplicate") == RawTransactionStatus.DUPLICATE
    assert raw_transaction_status_for_review_action("ignore") == RawTransactionStatus.IGNORED
    assert raw_transaction_status_for_review_action("mark_unique") == RawTransactionStatus.MATCHED
    assert (
        raw_transaction_status_for_review_action("needs_review")
        == RawTransactionStatus.NEEDS_REVIEW
    )


def test_reviewable_raw_transaction_statuses_include_normalized_rows() -> None:
    assert RawTransactionStatus.NORMALIZED in REVIEWABLE_RAW_TRANSACTION_STATUSES
    assert RawTransactionStatus.SUGGESTED in REVIEWABLE_RAW_TRANSACTION_STATUSES
    assert RawTransactionStatus.MATCHED in REVIEWABLE_RAW_TRANSACTION_STATUSES
    assert RawTransactionStatus.CONFIRMED not in REVIEWABLE_RAW_TRANSACTION_STATUSES
    assert RawTransactionStatus.IGNORED not in REVIEWABLE_RAW_TRANSACTION_STATUSES
    assert RawTransactionStatus.DUPLICATE not in REVIEWABLE_RAW_TRANSACTION_STATUSES


@pytest.mark.asyncio
async def test_review_status_marks_document_imported_when_last_row_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.features.imports.application.review import status as review_status

    workspace_id = uuid4()
    document_id = uuid4()
    raw_transaction_id = uuid4()
    raw_transaction = SimpleNamespace(id=raw_transaction_id, status=RawTransactionStatus.NORMALIZED)
    document = SimpleNamespace(
        id=document_id,
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        parse_attempts=[],
        raw_transactions=[
            SimpleNamespace(status=RawTransactionStatus.CONFIRMED),
            raw_transaction,
        ],
    )

    class FakeSession:
        committed = False

        async def commit(self) -> None:
            self.committed = True

    class FakeImportRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_raw_transaction_for_workspace(
            self,
            _workspace_id: UUID,
            _document_id: UUID,
            _raw_transaction_id: UUID,
        ) -> object:
            return raw_transaction

        async def mark_raw_transaction_status(
            self,
            raw_transaction_: Any,
            status: RawTransactionStatus,
        ) -> None:
            raw_transaction_.status = status

        async def get_document_for_workspace(
            self,
            _workspace_id: UUID,
            _document_id: UUID,
        ) -> object:
            return document

        async def mark_document_status(
            self,
            document_: Any,
            status: UploadedDocumentStatus,
        ) -> None:
            document_.status = status

    session = FakeSession()
    monkeypatch.setattr(review_status, "ImportRepository", FakeImportRepository)

    await RawTransactionReviewStatusUseCase(cast(Any, session)).set_status(
        workspace_id=workspace_id,
        document_id=document_id,
        raw_transaction_id=raw_transaction_id,
        action="ignore",
    )

    assert raw_transaction.status == RawTransactionStatus.IGNORED
    assert document.status == UploadedDocumentStatus.IMPORTED
    assert session.committed is True


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


def test_mark_raw_transaction_duplicate_preserves_review_message() -> None:
    raw_transaction = raw_transaction_from_values(normalization_error="Existing issue.")

    mark_raw_transaction_duplicate(
        raw_transaction,
        RawTransactionStatus.DUPLICATE,
        "Exact duplicate.",
    )

    assert raw_transaction.status == RawTransactionStatus.DUPLICATE
    assert raw_transaction.normalization_error == "Existing issue.; Exact duplicate."


def test_document_has_linked_operations_detects_confirmed_rows() -> None:
    raw_transaction = raw_transaction_from_values()
    document = RawTransactionDocumentStub(raw_transactions=[raw_transaction])

    assert document_has_linked_operations(document) is False

    raw_transaction.linked_operation_id = uuid4()
    assert document_has_linked_operations(document) is True


def test_review_redirect_url_avoids_anchor_jump() -> None:
    document_id = uuid4()
    raw_transaction_id = uuid4()

    assert review_row_anchor(raw_transaction_id) == f"raw-{raw_transaction_id}"
    assert review_redirect_url(document_id) == f"/imports/documents/{document_id}/review"


def test_review_item_vm_blocks_income_without_category() -> None:
    account_id = uuid4()
    row = review_row_stub(
        account_id=account_id,
        amount=Decimal("1500.00"),
        suggested_category_id=None,
    )

    item = build_review_item_for_test(row, accounts=[SimpleNamespace(id=account_id, name="Cash")])

    assert item.visual_state == "needs_review"
    assert item.is_confirmable is False
    assert item.primary_action is not None
    assert item.primary_action.id == "category_panel"
    assert any("категория" in problem.message for problem in item.problems)


def test_review_item_vm_marks_income_with_category_ready_to_confirm() -> None:
    account_id = uuid4()
    category_id = uuid4()
    row = review_row_stub(
        account_id=account_id,
        amount=Decimal("1500.00"),
        suggested_category_id=category_id,
    )

    item = build_review_item_for_test(
        row,
        accounts=[SimpleNamespace(id=account_id, name="Cash")],
        categories=[SimpleNamespace(id=category_id, name="Rent", system_key=None)],
    )

    assert item.visual_state == "ready_to_confirm"
    assert item.is_confirmable is True
    assert item.primary_action is not None
    assert item.primary_action.id == "confirm"
    assert item.primary_action.hidden_fields == {
        "action": "confirm",
        "category_id": str(category_id),
    }


def test_review_item_vm_blocks_transfer_between_same_account() -> None:
    account_id = uuid4()
    row = review_row_stub(
        account_id=account_id,
        amount=Decimal("-250.00"),
        suggested_operation_type=OperationType.TRANSFER,
        counterparty_account_id=account_id,
    )

    item = build_review_item_for_test(row, accounts=[SimpleNamespace(id=account_id, name="Card")])

    assert item.visual_state == "needs_review"
    assert item.is_confirmable is False
    assert any("отличаться" in problem.message for problem in item.problems)


def test_review_item_vm_action_hierarchy_separates_danger_actions() -> None:
    account_id = uuid4()
    category_id = uuid4()
    row = review_row_stub(
        account_id=account_id,
        amount=Decimal("-500.00"),
        suggested_category_id=category_id,
    )

    item = build_review_item_for_test(
        row,
        accounts=[SimpleNamespace(id=account_id, name="Card")],
        categories=[SimpleNamespace(id=category_id, name="Services", system_key=None)],
    )

    assert item.primary_action is not None
    assert item.visible_secondary_action is not None
    assert item.primary_action.placement == "primary"
    assert item.visible_secondary_action.placement == "secondary"
    assert len(item.danger_actions) == 1
    assert item.danger_actions[0].placement == "danger"
    assert item.danger_actions[0].confirm_message


def build_review_item_for_test(
    row: SimpleNamespace,
    *,
    accounts: list[SimpleNamespace] | None = None,
    categories: list[SimpleNamespace] | None = None,
) -> Any:
    document = SimpleNamespace(
        id=uuid4(),
        account_id=None,
        parse_attempts=[],
        raw_transactions=[row],
    )
    context = build_review_page_context(
        document=document,
        accounts=accounts or [],
        categories=categories or [],
        properties=[],
        transfer_suggestions={},
        existing_transfer_suggestions={},
    )
    return context.review_items_by_id[row.id]


def review_row_stub(
    *,
    account_id: UUID | None,
    amount: Decimal,
    suggested_category_id: UUID | None = None,
    suggested_operation_type: OperationType | None = None,
    counterparty_account_id: UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        row_index=1,
        status=RawTransactionStatus.NORMALIZED,
        account_id=account_id,
        counterparty_account_id=counterparty_account_id,
        operation_date=parse_bank_date("29.05.2026"),
        operation_date_raw=None,
        amount=amount,
        amount_raw=None,
        currency="RUB",
        description_normalized="Test row",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=None,
        suggested_category_id=suggested_category_id,
        suggested_property_id=None,
        suggested_operation_type=suggested_operation_type,
        linked_operation_id=None,
        linked_operation=None,
        raw_payload={},
    )


@pytest.mark.asyncio
async def test_confirm_with_remember_rule_reapplies_rules_to_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.features.imports.application.review import actions as review_actions

    calls: list[tuple[str, dict[str, object]]] = []

    class FakeRawTransactionPostingUseCase:
        def __init__(self, session: object) -> None:
            self.session = session

        async def post_raw_transaction(self, **kwargs: object) -> None:
            calls.append(("post", kwargs))

    class FakeTransactionRuleManagementUseCase:
        def __init__(self, session: object) -> None:
            self.session = session

        async def create_rule_from_raw_confirmation(self, **kwargs: object) -> None:
            calls.append(("create_rule", kwargs))

    class FakeTransactionRuleApplicationUseCase:
        def __init__(self, session: object) -> None:
            self.session = session

        async def apply_rules_to_document(self, **kwargs: object) -> SimpleNamespace:
            calls.append(("apply_rules", kwargs))
            return SimpleNamespace(updated_raw_transaction_ids=frozenset({uuid4()}))

    monkeypatch.setattr(
        review_actions,
        "RawTransactionPostingUseCase",
        FakeRawTransactionPostingUseCase,
    )
    monkeypatch.setattr(
        review_actions,
        "TransactionRuleManagementUseCase",
        FakeTransactionRuleManagementUseCase,
    )
    monkeypatch.setattr(
        review_actions,
        "TransactionRuleApplicationUseCase",
        FakeTransactionRuleApplicationUseCase,
    )

    workspace_id = uuid4()
    document_id = uuid4()
    raw_transaction_id = uuid4()
    category_id = uuid4()
    use_case = review_actions.RawTransactionReviewUseCase(
        session=cast(Any, object()),
        settings=cast(Any, object()),
    )

    result = await use_case.handle(
        context=cast(
            Any,
            SimpleNamespace(workspace=SimpleNamespace(id=workspace_id)),
        ),
        command=review_actions.RawTransactionReviewCommand(
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
            action="confirm",
            category_id=category_id,
            remember_rule=True,
            rule_pattern="KRASNOE&BELOE",
        ),
    )

    assert [name for name, _kwargs in calls] == ["post", "create_rule", "apply_rules"]
    assert result.updated_raw_transaction_ids
    assert calls[2][1] == {
        "workspace_id": workspace_id,
        "document_id": document_id,
    }


def raw_transaction_from_values(
    *,
    account_id: UUID | None = None,
    amount: Decimal | None = Decimal("10.00"),
    normalization_error: str | None = None,
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
        normalization_error=normalization_error,
    )


@dataclass(frozen=True)
class RawTransactionDocumentStub:
    raw_transactions: list[RawTransaction]
