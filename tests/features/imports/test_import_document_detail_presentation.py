from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from app.features.accounts.models import AccountType
from app.features.imports.application.documents.detail_view import (
    ImportAccountRef,
    ImportDocumentDetailView,
    ImportParseAttemptView,
    ImportRawTransactionRow,
)
from app.features.imports.models import (
    ParseAttemptStatus,
    RawTransactionStatus,
    UploadedDocumentStatus,
)
from app.features.imports.presentation.document_page.presenter import DocumentDetailPresenter


def document_view(
    *,
    status: UploadedDocumentStatus = UploadedDocumentStatus.REQUIRES_REVIEW,
    validation: dict[str, object] | None = None,
    raw_transactions: list[ImportRawTransactionRow] | None = None,
    parse_attempts: list[ImportParseAttemptView] | None = None,
    account: ImportAccountRef | None = None,
) -> ImportDocumentDetailView:
    return ImportDocumentDetailView(
        id=uuid4(),
        original_filename="statement.pdf",
        status=status,
        sha256_hash="a" * 64,
        storage_key="workspace/document/statement.pdf",
        bank_name=None,
        statement_type=None,
        account=account,
        validation=validation,
        raw_transactions=raw_transactions or [],
        parse_attempts=parse_attempts or [],
    )


def raw_transaction_row() -> ImportRawTransactionRow:
    return ImportRawTransactionRow(
        row_index=1,
        status=RawTransactionStatus.NORMALIZED,
        parse_attempt_id=uuid4(),
        display_date=date(2026, 6, 13),
        amount=Decimal("-42.00"),
        amount_raw="-42.00",
        currency="RUB",
        description="Оплата",
        normalization_error="",
    )


def failed_parse_attempt() -> ImportParseAttemptView:
    return ImportParseAttemptView(
        id=uuid4(),
        status=ParseAttemptStatus.FAILED,
        parser_name="expobank_card_statement_v1",
        parser_version="0.1",
        started_at=datetime(2026, 6, 13, 11, 5, 8),
        finished_at=datetime(2026, 6, 13, 11, 5, 8),
        error_message="PdfminerException: No /Root object!",
        validation_report=None,
        raw_tables=None,
        raw_text_by_page=None,
    )


def test_document_detail_presenter_routes_raw_rows_to_review() -> None:
    page = DocumentDetailPresenter().build(
        document_view(raw_transactions=[raw_transaction_row()]),
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
    assert page.parse_history_open is False


def test_document_detail_presenter_explains_empty_raw_rows_before_extraction() -> None:
    page = DocumentDetailPresenter().build(
        document_view(),
        can_manage_imports=True,
    )

    assert page.raw_empty_state.title == "Сырых строк пока нет"
    assert "Дождитесь извлечения" in page.raw_empty_state.message


def test_document_detail_presenter_opens_parse_history_for_failed_parse() -> None:
    page = DocumentDetailPresenter().build(
        document_view(
            status=UploadedDocumentStatus.FAILED_TO_PARSE,
            parse_attempts=[failed_parse_attempt()],
        ),
        can_manage_imports=True,
    )

    assert page.parse_history_open is True
    assert page.parse_history_count_label == "1 попытка"
    assert page.raw_empty_state.title == "Сырые строки не извлечены"


def test_document_detail_presenter_routes_unknown_statement_to_mapping() -> None:
    page = DocumentDetailPresenter().build(
        document_view(
            validation={
                "status": "needs_mapping",
                "message": (
                    "Parser is not available for this statement yet, but transaction-like tables "
                    "were extracted. Configure column mapping to import it."
                ),
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
    assert page.raw_empty_state.title == "Строки появятся после настройки"
    assert "импортируйте строки в проверку" in page.raw_empty_state.message
    assert page.validation.message == (
        "Для этой выписки пока нет готового парсера, но найдены таблицы, похожие "
        "на операции. Настройте колонки, чтобы импортировать строки."
    )
    assert [(metric.label, metric.value) for metric in page.validation.metrics] == [
        ("банк", "Ozon Bank"),
        ("тип", "карточная выписка"),
        ("извлечение", "текстовый"),
        ("таблицы", 3),
    ]


def test_document_detail_presenter_hides_management_actions_without_permission() -> None:
    page = DocumentDetailPresenter().build(
        document_view(raw_transactions=[raw_transaction_row()]),
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


def test_document_detail_presenter_builds_account_reference() -> None:
    account_id = uuid4()

    page = DocumentDetailPresenter().build(
        document_view(
            account=ImportAccountRef(
                id=account_id,
                name="ВТБ вклад",
                type=AccountType.DEPOSIT,
                currency="RUB",
            )
        ),
        can_manage_imports=True,
    )

    assert page.account is not None
    assert page.account.id == account_id
    assert page.account.name == "ВТБ вклад"
    assert page.account.type_label == "депозит"
    assert page.account.currency == "RUB"
    assert page.technical_details.document_items[-1].label == "ID счета"
    assert page.technical_details.document_items[-1].value == account_id


def test_document_detail_presenter_builds_parse_attempt_summaries_and_debug() -> None:
    attempt_id = uuid4()
    validation_report: dict[str, object] = {
        "status": "failed",
        "message": "Rows are not readable.",
    }
    raw_tables: list[dict[str, object]] = [{"page": 1, "rows": [["Дата", "Сумма"]]}]
    raw_text_by_page = ["statement text"]

    page = DocumentDetailPresenter().build(
        document_view(
            parse_attempts=[
                ImportParseAttemptView(
                    id=attempt_id,
                    status=ParseAttemptStatus.FAILED,
                    parser_name="expobank_card_statement_v1",
                    parser_version="0.1",
                    started_at=datetime(2026, 6, 13, 11, 5, 8),
                    finished_at=None,
                    error_message=None,
                    validation_report=validation_report,
                    raw_tables=raw_tables,
                    raw_text_by_page=raw_text_by_page,
                )
            ]
        ),
        can_manage_imports=True,
    )

    assert len(page.parse_attempts) == 1
    assert page.parse_attempts[0].status_label == "ошибка"
    assert page.parse_attempts[0].parser_label == "expobank_card_statement_v1 0.1"
    assert page.parse_attempts[0].message == "Rows are not readable."

    assert len(page.technical_details.parse_attempts) == 1
    debug = page.technical_details.parse_attempts[0]
    assert debug.id == attempt_id
    assert debug.title == "Попытка парсинга ошибка"
    assert debug.validation_report == validation_report
    assert debug.raw_tables == raw_tables
    assert debug.raw_text_by_page == raw_text_by_page


def test_document_detail_presenter_builds_raw_transaction_rows() -> None:
    page = DocumentDetailPresenter().build(
        document_view(raw_transactions=[raw_transaction_row()]),
        can_manage_imports=True,
    )

    assert len(page.raw_transactions) == 1
    row = page.raw_transactions[0]
    assert row.row_index == 1
    assert row.status_label == "нормализовано"
    assert row.status_css_class == "badge-normalized"
    assert row.amount_label == Decimal("-42.00")
    assert row.amount_tone == "expense"
    assert row.currency == "RUB"


def test_document_detail_presenter_builds_unknown_statement_table_previews() -> None:
    page = DocumentDetailPresenter().build(
        document_view(
            validation={
                "status": "needs_mapping",
                "message": "Configure columns.",
                "detected_bank_name": None,
                "detected_statement_type": None,
                "text_based": True,
                "table_count": 1,
                "table_previews": [
                    {
                        "page_number": 2,
                        "table_index": 0,
                        "row_count": 8,
                        "preview_row_count": 5,
                        "column_count": 4,
                        "rows": [["30.05.2026", "Оплата", "-390,00"]],
                        "is_continuation": True,
                        "continued_from_page_number": 1,
                        "continued_from_table_index": 0,
                        "continuation_mapping_fields": [
                            {"field": "operation_date", "column_index": 0},
                            {"field": "amount", "column_index": 2},
                        ],
                    }
                ],
            }
        ),
        can_manage_imports=True,
    )

    assert page.validation is not None
    assert [(metric.label, metric.value) for metric in page.validation.metrics] == [
        ("банк", "не определен"),
        ("извлечение", "текстовый"),
        ("таблицы", 1),
    ]
    preview = page.validation.table_previews[0]
    assert preview.meta == [
        "страница 2",
        "таблица 1",
        "показано 5 из 8 строк",
        "4 колонок",
    ]
    assert preview.continuation_summary == "Продолжение таблицы · страница 1 · таблица 1"
    assert [(field.label, field.column_number) for field in preview.continuation_fields] == [
        ("дата", 1),
        ("сумма", 3),
    ]


def test_document_detail_presenter_builds_mapping_suggestion_vm() -> None:
    page = DocumentDetailPresenter().build(
        document_view(
            validation={
                "status": "needs_mapping",
                "message": "Configure columns.",
                "detected_bank_name": None,
                "detected_statement_type": None,
                "text_based": True,
                "table_count": 1,
                "table_previews": [
                    {
                        "page_number": 1,
                        "table_index": 0,
                        "row_count": 2,
                        "preview_row_count": 2,
                        "column_count": 4,
                        "rows": [["Дата операции", "Описание", "Документ", "Сумма операции"]],
                        "mapping_suggestions": [
                            {
                                "confidence": 0.91,
                                "reasons": [
                                    {
                                        "field": "operation_date",
                                        "column_index": 0,
                                        "header": "Дата операции",
                                        "evidence": "header_match",
                                    },
                                    {
                                        "field": "amount",
                                        "column_index": 3,
                                        "evidence": "money_like_values",
                                        "matched_count": 2,
                                        "sample_count": 3,
                                    },
                                ],
                                "warnings": [
                                    {
                                        "code": "partial_debit_credit_columns",
                                        "fields": ["debit_amount"],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ),
        can_manage_imports=True,
    )

    assert page.validation is not None
    suggestion = page.validation.table_previews[0].primary_mapping_suggestion
    assert suggestion is not None
    assert suggestion.title == "Предложение маппинга · 91%"
    assert [reason.message for reason in suggestion.reasons] == [
        "дата: колонка 1 выбрана по заголовку «Дата операции».",
        "сумма: колонка 4 содержит 2/3 значений, похожих на суммы.",
    ]
    assert [warning.message for warning in suggestion.warnings] == [
        "Найдена только одна колонка списания/зачисления. Проверьте знак суммы перед импортом."
    ]
