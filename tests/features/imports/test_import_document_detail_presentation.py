from uuid import uuid4

from app.features.imports.mapping.dto import ImportDocumentDetailView
from app.features.imports.models import UploadedDocumentStatus
from app.features.imports.presentation.document_detail import DocumentDetailPresenter


def document_view(
    *,
    status: UploadedDocumentStatus = UploadedDocumentStatus.REQUIRES_REVIEW,
    validation: dict[str, object] | None = None,
    raw_transactions: list[object] | None = None,
) -> ImportDocumentDetailView:
    return ImportDocumentDetailView(
        id=uuid4(),
        original_filename="statement.pdf",
        status=status,
        sha256_hash="a" * 64,
        storage_key="workspace/document/statement.pdf",
        bank_name=None,
        statement_type=None,
        account=None,
        validation=validation,
        raw_transactions=raw_transactions or [],
        parse_attempts=[],
    )


def test_document_detail_presenter_routes_raw_rows_to_review() -> None:
    page = DocumentDetailPresenter().build(
        document_view(raw_transactions=[object()]),
        can_manage_imports=True,
    )

    assert page.status_label == "нужна проверка"
    assert page.workflow.review == "current"
    assert page.next_step.title == "Проверьте строки"
    assert page.next_step.primary_label == "открыть проверку"
    assert [action.label for action in page.actions] == [
        "перепарсить",
        "игнорировать",
        "удалить",
    ]


def test_document_detail_presenter_routes_unknown_statement_to_mapping() -> None:
    page = DocumentDetailPresenter().build(
        document_view(
            validation={
                "status": "needs_mapping",
                "message": "Configure column mapping to import it.",
                "detected_bank_name": "Ozon Bank",
                "detected_statement_type": "card_statement",
                "text_based": True,
                "table_count": 3,
            }
        ),
        can_manage_imports=True,
    )

    assert page.workflow.mapping == "current"
    assert page.next_step.title == "Настройте колонки"
    assert page.validation is not None
    assert page.validation.needs_mapping is True
    assert [(metric.label, metric.value) for metric in page.validation.metrics] == [
        ("банк", "Ozon Bank"),
        ("тип", "карточная выписка"),
        ("извлечение", "текстовый"),
        ("таблицы", 3),
    ]


def test_document_detail_presenter_hides_management_actions_without_permission() -> None:
    page = DocumentDetailPresenter().build(
        document_view(raw_transactions=[object()]),
        can_manage_imports=False,
    )

    assert page.actions == []
    assert page.next_step.primary_href == "/imports"
    assert page.next_step.primary_label == "к списку импортов"


def test_document_detail_presenter_marks_imported_document_done() -> None:
    page = DocumentDetailPresenter().build(
        document_view(status=UploadedDocumentStatus.IMPORTED),
        can_manage_imports=True,
    )

    assert page.status_label == "импортирован"
    assert page.workflow.review == "done"
    assert page.workflow.ledger == "done"
