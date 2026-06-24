from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.imports.models import RawTransactionStatus, UploadedDocumentStatus
from app.templating import create_templates


def render_template(template_name: str, **context: object) -> str:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")
    context.setdefault("css_version", "test-css-version")
    return templates.env.get_template(template_name).render(**context)


def test_import_index_guides_to_review_when_document_needs_attention() -> None:
    document_id = uuid4()
    html = render_template(
        "imports/index.html",
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        documents=[
            SimpleNamespace(
                id=document_id,
                original_filename="statement.pdf",
                status=UploadedDocumentStatus.REQUIRES_REVIEW,
                file_size_bytes=1024,
                created_at="2026-06-24",
            )
        ],
    )

    assert "следующий шаг" in html
    assert "Проверьте выписку" in html
    assert f"/imports/documents/{document_id}/review" in html


def test_import_index_guides_to_upload_when_no_documents_exist() -> None:
    html = render_template(
        "imports/index.html",
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        documents=[],
    )

    assert "Выписки еще не загружены" in html
    assert "empty-state-copy" in html
    assert "следующий шаг" not in html
    assert "/imports/upload" in html


def test_upload_page_guides_to_account_before_upload() -> None:
    html = render_template(
        "imports/upload.html",
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        accounts=[],
        error=None,
    )

    assert "Сначала нужен счет" in html
    assert "empty-state-copy" in html
    assert "следующий шаг" not in html
    assert "/accounts" in html


def test_upload_page_guides_to_file_when_accounts_exist() -> None:
    html = render_template(
        "imports/upload.html",
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal"),
        accounts=[SimpleNamespace(id=uuid4(), name="Карта", currency="RUB")],
        error=None,
    )

    assert "Выберите счет и файл" in html
    assert "#statement_pdf" in html


def test_document_detail_guides_to_mapping_when_columns_are_unknown() -> None:
    document_id = uuid4()
    html = render_template(
        "imports/detail.html",
        app_name="Booker Tee",
        view=document_view(
            document_id=document_id,
            status=UploadedDocumentStatus.REQUIRES_REVIEW,
            validation={
                "status": "needs_mapping",
                "message": "Configure columns.",
                "detected_bank_name": None,
                "detected_statement_type": None,
                "text_based": True,
                "table_count": 1,
                "table_previews": [],
            },
        ),
    )

    assert "Настройте колонки" in html
    assert f"/imports/documents/{document_id}/mapping" in html
    assert "workflow-step-current" in html
    assert "Настройка" in html


def test_document_detail_guides_to_review_when_rows_exist() -> None:
    document_id = uuid4()
    html = render_template(
        "imports/detail.html",
        app_name="Booker Tee",
        view=document_view(
            document_id=document_id,
            status=UploadedDocumentStatus.REQUIRES_REVIEW,
            validation={
                "status": "valid",
                "message": "Ready.",
                "extracted_count": 1,
                "calculated_total_inflow": "0.00",
                "calculated_total_outflow": "100.00",
                "currency": "RUB",
            },
            raw_transactions=[raw_row(RawTransactionStatus.NORMALIZED)],
        ),
    )

    assert "Проверьте строки" in html
    assert f"/imports/documents/{document_id}/review" in html
    assert "workflow-step-current" in html
    assert "Проверка" in html


def test_review_page_guides_to_first_remaining_row() -> None:
    document_id = uuid4()
    confirmed_row = raw_row(RawTransactionStatus.CONFIRMED)
    remaining_row = raw_row(RawTransactionStatus.NORMALIZED)
    html = render_template(
        "imports/review.html",
        app_name="Booker Tee",
        document=SimpleNamespace(
            id=document_id,
            original_filename="statement.pdf",
            status=UploadedDocumentStatus.REQUIRES_REVIEW,
            parse_attempts=[],
            raw_transactions=[confirmed_row, remaining_row],
        ),
        categories=[],
        properties=[],
        accounts=[],
        transfer_suggestions={},
    )

    assert "Продолжайте проверку" in html
    assert "Осталось обработать 1 из 2 строк." in html
    assert f"#raw-{remaining_row.id}" in html
    assert "workflow-step-current" in html


def test_review_page_guides_from_empty_raw_rows_to_document() -> None:
    document_id = uuid4()
    html = render_template(
        "imports/review.html",
        app_name="Booker Tee",
        document=SimpleNamespace(
            id=document_id,
            original_filename="statement.pdf",
            status=UploadedDocumentStatus.REQUIRES_REVIEW,
            parse_attempts=[],
            raw_transactions=[],
        ),
        categories=[],
        properties=[],
        accounts=[],
        transfer_suggestions={},
    )

    assert "Сырых строк пока нет" in html
    assert "возможно, нужно настроить колонки" in html
    assert f"/imports/documents/{document_id}" in html
    assert "/imports/upload" in html
    assert "empty-state-copy" in html


def test_dashboard_uses_guided_empty_states() -> None:
    html = render_template(
        "dashboard/summary.html",
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal", default_currency="RUB"),
        overview=SimpleNamespace(
            month_start="01.06.2026",
            month_end="30.06.2026",
            documents_needing_review=[],
            recent_documents=[],
            reports=SimpleNamespace(
                summary=SimpleNamespace(
                    income=Decimal("0.00"),
                    expense=Decimal("0.00"),
                    profit=Decimal("0.00"),
                ),
                account_balances=[],
            ),
        ),
    )

    assert "Счетов пока нет" in html
    assert "Загруженных выписок пока нет" in html
    assert "Первые шаги" in html
    assert "Рабочее пространство" in html
    assert "Добавьте счет" in html
    assert "onboarding-item-current" in html
    assert "следующий шаг" not in html
    assert html.count("empty-state-copy") == 2


def test_dashboard_index_is_full_page_with_navigation_and_checklist() -> None:
    html = render_template(
        "dashboard/index.html",
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal", default_currency="RUB"),
        overview=incomplete_dashboard_overview(),
    )

    assert "<title>Обзор · Booker Tee</title>" in html
    assert 'href="/dashboard"' in html
    assert 'href="/css/app.css?v=test-css-version"' in html
    assert "Первые шаги" in html
    assert "onboarding-list" in html


def test_dashboard_hides_onboarding_checklist_after_setup_is_complete() -> None:
    account_id = uuid4()
    document_id = uuid4()
    html = render_template(
        "dashboard/summary.html",
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal", default_currency="RUB"),
        overview=SimpleNamespace(
            month_start="01.06.2026",
            month_end="30.06.2026",
            documents_needing_review=[],
            recent_documents=[
                SimpleNamespace(
                    id=document_id,
                    original_filename="statement.pdf",
                    status=UploadedDocumentStatus.IMPORTED,
                )
            ],
            reports=SimpleNamespace(
                summary=SimpleNamespace(
                    income=Decimal("100.00"),
                    expense=Decimal("40.00"),
                    profit=Decimal("60.00"),
                ),
                account_balances=[
                    SimpleNamespace(
                        account=SimpleNamespace(id=account_id, name="Карта", currency="RUB"),
                        balance=Decimal("60.00"),
                    )
                ],
                categories=[
                    SimpleNamespace(
                        category_id=uuid4(),
                        category_name="Продукты",
                        income=Decimal("0.00"),
                        expense=Decimal("40.00"),
                        profit=Decimal("-40.00"),
                    )
                ],
                properties=[],
                uncategorized=[],
            ),
        ),
    )

    assert "Первые шаги" not in html
    assert "onboarding-list" not in html
    assert "Откройте отчеты" in html


def test_review_page_shows_inline_safety_hints() -> None:
    row = raw_row(RawTransactionStatus.NORMALIZED)
    html = render_template(
        "imports/review.html",
        app_name="Booker Tee",
        document=SimpleNamespace(
            id=uuid4(),
            original_filename="statement.pdf",
            status=UploadedDocumentStatus.REQUIRES_REVIEW,
            parse_attempts=[],
            raw_transactions=[row],
        ),
        categories=[],
        properties=[],
        accounts=[],
        transfer_suggestions={},
    )

    assert "похожие описания должны получать такую же категорию" in html
    assert "не влияет на прибыль" in html
    assert "inline-hint" in html


def incomplete_dashboard_overview() -> SimpleNamespace:
    return SimpleNamespace(
        month_start="01.06.2026",
        month_end="30.06.2026",
        documents_needing_review=[],
        recent_documents=[],
        reports=SimpleNamespace(
            summary=SimpleNamespace(
                income=Decimal("0.00"),
                expense=Decimal("0.00"),
                profit=Decimal("0.00"),
            ),
            account_balances=[],
            categories=[],
            properties=[],
            uncategorized=[],
        ),
    )


def test_review_page_shows_possible_duplicate_hint() -> None:
    html = render_template(
        "imports/review.html",
        app_name="Booker Tee",
        document=SimpleNamespace(
            id=uuid4(),
            original_filename="statement.pdf",
            status=UploadedDocumentStatus.REQUIRES_REVIEW,
            parse_attempts=[],
            raw_transactions=[raw_row(RawTransactionStatus.POSSIBLE_DUPLICATE)],
        ),
        categories=[],
        properties=[],
        accounts=[],
        transfer_suggestions={},
    )

    assert "Дубли не должны попадать в отчеты повторно" in html


def test_review_page_guides_to_reports_when_import_is_done() -> None:
    html = render_template(
        "imports/review.html",
        app_name="Booker Tee",
        document=SimpleNamespace(
            id=uuid4(),
            original_filename="statement.pdf",
            status=UploadedDocumentStatus.IMPORTED,
            parse_attempts=[],
            raw_transactions=[
                raw_row(RawTransactionStatus.CONFIRMED),
                raw_row(RawTransactionStatus.IGNORED),
            ],
        ),
        categories=[],
        properties=[],
        accounts=[],
        transfer_suggestions={},
    )

    assert "Импорт разобран" in html
    assert "/reports" in html
    assert html.count("workflow-step-done") >= 4


def test_mapping_page_shows_mapping_as_current_workflow_step() -> None:
    document_id = uuid4()
    html = render_template(
        "imports/mapping.html",
        app_name="Booker Tee",
        view=document_view(
            document_id=document_id,
            status=UploadedDocumentStatus.REQUIRES_REVIEW,
            validation={"status": "needs_mapping"},
        ),
        command=SimpleNamespace(
            page_number=1,
            table_index=0,
            operation_date_column=0,
            posting_date_column=None,
            description_column=1,
            amount_column=2,
            debit_amount_column=None,
            credit_amount_column=None,
            currency_column=None,
            balance_after_column=None,
            first_data_row=1,
            default_currency="RUB",
        ),
        preview=None,
        selected_table={
            "column_count": 0,
            "rows": [],
            "row_count": 0,
            "page_number": 1,
            "table_index": 0,
        },
        table_options=[],
        compatible_table_count=0,
        mapping_templates=[],
    )

    assert "workflow-step-current" in html
    assert "Настройка" in html
    assert "Вернитесь к документу" in html
    assert f"/imports/documents/{document_id}" in html


def document_view(
    *,
    document_id: object,
    status: UploadedDocumentStatus,
    validation: dict[str, object] | None,
    raw_transactions: list[object] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=document_id,
        original_filename="statement.pdf",
        status=status,
        sha256_hash="a" * 64,
        storage_key="workspace/document/statement.pdf",
        account=None,
        validation=validation,
        raw_transactions=raw_transactions or [],
        parse_attempts=[],
    )


def raw_row(status: RawTransactionStatus) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        row_index=1,
        status=status,
        operation_date="2026-06-24",
        operation_date_raw=None,
        display_date="24.06.2026",
        amount=Decimal("-100.00"),
        amount_raw=None,
        currency="RUB",
        description="Покупка",
        description_normalized="Покупка",
        description_raw=None,
        normalization_error=None,
        suggested_by_rule_id=None,
        suggested_category_id=None,
        suggested_property_id=None,
        linked_operation_id=None,
        raw_payload={},
    )
