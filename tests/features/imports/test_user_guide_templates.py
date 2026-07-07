from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.imports.models import RawTransactionStatus, UploadedDocumentStatus
from app.features.imports.presentation.document_page.presenter import DocumentDetailPresenter
from app.features.imports.presentation.mapping.models import MappingDocumentVM, MappingNextStepVM
from app.features.imports.presentation.review.page import build_review_page_context
from app.features.workspaces.models import WorkspaceType
from app.templating import create_templates


def render_template(template_name: str, **context: object) -> str:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")
    context.setdefault("css_version", "test-css-version")
    return templates.env.get_template(template_name).render(**context)


def render_review_template(*, document: object) -> str:
    templates = create_templates()
    cast(Any, templates.env.globals)["url_for"] = lambda _name, **values: values.get("path", "")
    page_context = build_review_page_context(
        document=document,
        accounts=[],
        categories=[],
        properties=[],
        transfer_suggestions={},
        existing_transfer_suggestions={},
    )
    return templates.env.get_template("imports/review.html").render(
        **page_context.template_values(
            app_name="Booker Tee",
            workspace=SimpleNamespace(id=uuid4(), name="Personal"),
        ),
        css_version="test-css-version",
    )


def render_document_detail_template(*, view: object) -> str:
    return render_template(
        "imports/detail.html",
        app_name="Booker Tee",
        page=DocumentDetailPresenter().build(
            cast(Any, view),
            can_manage_imports=True,
        ),
    )


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
    assert "загрузить базовые правила" in html
    assert "inline-hint" in html
    assert "file-upload-control" in html
    assert "выбрать файл" in html
    assert "файл не выбран" in html
    assert "Поддержка в альфе" in html
    assert "PDF, XLSX" in html
    assert "Альфа-Банк XLSX" in html
    assert "Ozon Банк" in html
    assert "T-Банк" in html
    assert "Сбербанк" in html
    assert "ВТБ" in html
    assert "Экспобанк" in html
    assert "настроить колонки вручную" in html
    assert "следующий шаг" not in html


def test_document_detail_guides_to_mapping_when_columns_are_unknown() -> None:
    document_id = uuid4()
    html = render_document_detail_template(
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
    html = render_document_detail_template(
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
    html = render_review_template(
        document=SimpleNamespace(
            id=document_id,
            original_filename="statement.pdf",
            status=UploadedDocumentStatus.REQUIRES_REVIEW,
            parse_attempts=[],
            raw_transactions=[confirmed_row, remaining_row],
        ),
    )

    assert "Продолжайте проверку" in html
    assert "Осталось обработать 1 из 2 строк." in html
    assert "review-rule-hint" in html
    assert "review-support-card" in html
    assert "review-support-actions" in html
    assert "Подсказки категорий можно применить к этой выписке." in html
    assert 'href="/rules"' in html
    assert f'action="/imports/documents/{document_id}/apply-rules"' in html
    assert "применить" in html
    assert f"#raw-{remaining_row.id}" in html
    assert "workflow-step-current" in html


def test_review_page_guides_from_empty_raw_rows_to_document() -> None:
    document_id = uuid4()
    html = render_review_template(
        document=SimpleNamespace(
            id=document_id,
            original_filename="statement.pdf",
            status=UploadedDocumentStatus.REQUIRES_REVIEW,
            parse_attempts=[],
            raw_transactions=[],
        ),
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
            month_start=date(2026, 6, 1),
            month_end=date(2026, 6, 30),
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
    assert "01.06.2026 — 30.06.2026" in html
    assert "2026-06-01" not in html
    assert "onboarding-item-current" in html
    assert "следующий шаг" not in html
    assert html.count("empty-state-copy") == 2


def test_dashboard_index_is_full_page_with_navigation_and_checklist() -> None:
    html = render_template(
        "dashboard/index.html",
        app_name="Booker Tee",
        current_user=SimpleNamespace(name="Test", email="test@example.com"),
        current_workspace=SimpleNamespace(name="Personal"),
        workspace=SimpleNamespace(name="Personal", default_currency="RUB"),
        overview=incomplete_dashboard_overview(),
    )

    assert "<title>Обзор · Booker Tee</title>" in html
    assert '<a class="brand" href="/dashboard">Booker Tee</a>' in html
    assert 'href="/dashboard"' in html
    assert 'href="/css/app.css?v=test-css-version"' in html
    assert "Первые шаги" in html
    assert "onboarding-list" in html


def test_public_home_focuses_on_auth_before_private_setup_steps() -> None:
    html = render_template(
        "home.html",
        app_name="Booker Tee",
        current_user=None,
        current_workspace=None,
    )

    assert "header-grid-public" in html
    assert '<a class="brand" href="/">Booker Tee</a>' in html
    assert 'href="/login"' in html
    assert 'href="/signup"' in html
    assert 'href="/accounts"' not in html
    assert 'href="/imports/upload"' not in html
    assert "Добавить счета после входа" in html


def test_profile_separates_session_action_from_profile_metrics() -> None:
    html = render_template(
        "users/index.html",
        app_name="Booker Tee",
        current_user=SimpleNamespace(name="Test User", email="test@example.com"),
        workspace=SimpleNamespace(name="Personal"),
    )

    assert "session-actions" in html
    assert 'action="/logout"' in html
    assert "form-panel" not in html
    assert 'class="truncate-label" title="test@example.com"' in html


def test_workspaces_keep_editing_in_secondary_admin_layer() -> None:
    current_workspace_id = uuid4()
    other_workspace_id = uuid4()
    html = render_template(
        "workspaces/index.html",
        app_name="Booker Tee",
        current_user=SimpleNamespace(name="Test User", email="test@example.com"),
        workspace=SimpleNamespace(
            id=current_workspace_id,
            name="Personal",
            default_currency="RUB",
        ),
        workspace_types=list(WorkspaceType),
        workspace_return_path="/imports",
        workspaces=[
            SimpleNamespace(
                id=current_workspace_id,
                name="Personal",
                type=WorkspaceType.PERSONAL,
                default_currency="RUB",
            ),
            SimpleNamespace(
                id=other_workspace_id,
                name="Family Budget",
                type=WorkspaceType.FAMILY,
                default_currency="RUB",
            ),
        ],
    )

    assert "admin-details" in html
    assert "Редактирование" in html
    assert f'action="/workspaces/{other_workspace_id}/select"' in html
    assert 'name="next" value="/imports"' in html
    assert f'action="/workspaces/{current_workspace_id}/select"' not in html


def test_workspace_invitation_link_is_visible_after_creation() -> None:
    workspace_id = uuid4()
    invitation_link = "http://testserver/workspaces/invitations/invite-token"

    html = render_template(
        "workspaces/index.html",
        app_name="Booker Tee",
        current_user=SimpleNamespace(name="Test User", email="test@example.com"),
        workspace=SimpleNamespace(
            id=workspace_id,
            name="Family",
            default_currency="RUB",
        ),
        workspace_types=list(WorkspaceType),
        workspaces=[],
        can_invite_members=True,
        created_invitation_link=invitation_link,
        created_invitation_expires_at=date(2026, 7, 3),
        invite_roles=[],
        members=[],
        pending_invitations=[],
        audit_events=[],
    )

    assert "Ссылка-приглашение создана" in html
    assert "Показывается один раз" in html
    assert f'value="{invitation_link}"' in html
    assert "копировать" in html


def test_dashboard_review_metric_links_to_first_document_requiring_review() -> None:
    document_id = uuid4()
    html = render_template(
        "dashboard/summary.html",
        app_name="Booker Tee",
        workspace=SimpleNamespace(name="Personal", default_currency="RUB"),
        overview=SimpleNamespace(
            month_start="01.06.2026",
            month_end="30.06.2026",
            documents_needing_review=[SimpleNamespace(id=document_id)],
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
        ),
    )

    assert "metric-review-action" in html
    assert f'href="/imports/documents/{document_id}/review"' in html
    assert "проверить строки" in html


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


def test_review_page_shows_review_panels_without_inline_safety_copy() -> None:
    row = raw_row(RawTransactionStatus.NORMALIZED)
    html = render_review_template(
        document=SimpleNamespace(
            id=uuid4(),
            original_filename="statement.pdf",
            status=UploadedDocumentStatus.REQUIRES_REVIEW,
            parse_attempts=[],
            raw_transactions=[row],
        ),
    )

    assert "Категория" in html
    assert "основной разбор строки" in html
    assert "Перевод" in html
    assert "если это перемещение между счетами" in html
    assert "похожие описания должны получать такую же категорию" not in html


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


def test_review_page_shows_possible_duplicate_actions() -> None:
    html = render_review_template(
        document=SimpleNamespace(
            id=uuid4(),
            original_filename="statement.pdf",
            status=UploadedDocumentStatus.REQUIRES_REVIEW,
            parse_attempts=[],
            raw_transactions=[raw_row(RawTransactionStatus.POSSIBLE_DUPLICATE)],
        ),
    )

    assert "возможный дубль" in html
    assert "Это новая операция" in html
    assert "На проверку" in html
    assert "Игнорировать" in html
    assert "Сравнить" not in html


def test_review_page_guides_to_reports_when_import_is_done() -> None:
    html = render_review_template(
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
    )

    assert "Импорт разобран" in html
    assert "/reports" in html
    assert html.count("workflow-step-done") >= 4


def test_mapping_page_shows_mapping_as_current_workflow_step() -> None:
    document_id = uuid4()
    html = render_template(
        "imports/mapping.html",
        app_name="Booker Tee",
        page=SimpleNamespace(
            document=MappingDocumentVM(
                status_label="требует проверки",
                filename="statement.pdf",
                detail_url=f"/imports/documents/{document_id}",
                preview_url=f"/imports/documents/{document_id}/mapping",
                import_url=f"/imports/documents/{document_id}/mapping/import",
            ),
            next_step=MappingNextStepVM(
                title="Вернитесь к документу",
                message=(
                    "Таблицы для настройки не найдены. Проверьте детали парсинга "
                    "или загрузите выписку заново."
                ),
                primary_href=f"/imports/documents/{document_id}",
                primary_label="открыть документ",
                primary_icon="file-text",
                secondary_href="/imports/upload",
                secondary_label="загрузить заново",
                secondary_icon="upload",
            ),
            template_notice=None,
            table_picker_options=[],
        ),
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
        parse_attempt_id=uuid4(),
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
