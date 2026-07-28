from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI

from api_client import ApiTestClient as TestClient
from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.v1.imports.dependencies import get_import_document_list_reader
from app.features.imports.application.documents.listing import (
    ImportDocumentListAccountRow,
    ImportDocumentListFilters,
    ImportDocumentListPagination,
    ImportDocumentListReader,
    ImportDocumentListRow,
    ImportDocumentListSummaryRow,
)
from app.features.imports.models import ParseAttemptStatus, UploadedDocumentStatus
from app.features.users.models import User
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.service import WorkspaceContext
from app.main import create_app


class DocumentListSourceStub:
    def __init__(self, rows: list[ImportDocumentListRow]) -> None:
        self.rows = rows
        self.workspace_ids: list[UUID] = []
        self.filters: list[ImportDocumentListFilters] = []
        self.paginations: list[ImportDocumentListPagination] = []

    async def list_document_rows_for_workspace(
        self,
        *,
        workspace_id: UUID,
        filters: ImportDocumentListFilters,
        pagination: ImportDocumentListPagination,
    ) -> list[ImportDocumentListRow]:
        self.workspace_ids.append(workspace_id)
        self.filters.append(filters)
        self.paginations.append(pagination)
        return self.rows

    async def count_document_rows_for_workspace(
        self,
        *,
        workspace_id: UUID,
        filters: ImportDocumentListFilters,
    ) -> int:
        self.workspace_ids.append(workspace_id)
        self.filters.append(filters)
        return len(self.rows)

    async def list_document_filter_accounts_for_workspace(
        self,
        workspace_id: UUID,
    ) -> list[ImportDocumentListAccountRow]:
        self.workspace_ids.append(workspace_id)
        row = self.rows[0] if self.rows else None
        if row is None or row.account_id is None:
            return []
        return [
            ImportDocumentListAccountRow(
                id=row.account_id,
                name=row.account_name or "Основной",
                currency=row.account_currency or "RUB",
                bank_name=row.account_bank_name,
            )
        ]

    async def summarize_documents_for_workspace(
        self,
        workspace_id: UUID,
    ) -> ImportDocumentListSummaryRow:
        self.workspace_ids.append(workspace_id)
        return ImportDocumentListSummaryRow(
            total_document_count=len(self.rows),
            attention_document_count=len(self.rows),
        )


def test_import_documents_returns_typed_workspace_list() -> None:
    row = document_row()
    app, source, workspace_id = import_documents_app([row])

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/imports/documents"
            f"?state=attention&account_id={row.account_id}"
            "&period_from=2026-07-01&period_to=2026-07-31"
            "&sort=created_at_asc&page=2&per_page=50"
        )

    assert response.status_code == 200
    assert response.json() == {
        "workspaceId": str(workspace_id),
        "workspaceName": "Дом",
        "items": [
            {
                "id": str(row.id),
                "filename": "statement.pdf",
                "status": "requires_review",
                "createdAt": "2026-07-24T10:00:00Z",
                "fileSizeBytes": 2048,
                "detectedBankName": "Альфа-Банк",
                "statementPeriod": {
                    "start": "2026-07-01",
                    "end": "2026-07-31",
                },
                "account": {
                    "id": str(row.account_id),
                    "name": "Основной",
                    "currency": "RUB",
                    "bankName": "Альфа-Банк",
                },
                "totalRowCount": 0,
                "reviewableRowCount": 0,
                "capabilities": {
                    "canOpenDetail": True,
                    "canMap": True,
                    "canReview": False,
                },
                "nextStepKind": "mapping",
            }
        ],
        "pagination": {
            "page": 1,
            "perPage": 50,
            "total": 1,
            "totalPages": 1,
            "hasPrevious": False,
            "hasNext": False,
        },
        "filterOptions": {
            "accounts": [
                {
                    "id": str(row.account_id),
                    "name": "Основной",
                    "currency": "RUB",
                    "bankName": "Альфа-Банк",
                }
            ],
            "perPage": [25, 50, 100],
        },
        "summary": {
            "totalDocumentCount": 1,
            "attentionDocumentCount": 1,
        },
        "capabilities": {
            "canUpload": True,
            "readonlyReasonCode": None,
        },
    }
    assert source.workspace_ids == [workspace_id] * 4
    assert source.filters[0].account_id == row.account_id
    assert source.filters[0].period_from == date(2026, 7, 1)
    assert source.filters[0].period_to == date(2026, 7, 31)
    assert source.paginations == [ImportDocumentListPagination(page=1, per_page=50)]


def test_import_documents_is_readonly_for_viewer_without_hiding_data() -> None:
    app, _, _ = import_documents_app([document_row()], role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.get("/api/v1/imports/documents")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["capabilities"] == {
        "canUpload": False,
        "readonlyReasonCode": "import_management_forbidden",
    }
    assert payload["items"][0]["capabilities"]["canMap"] is False
    assert payload["items"][0]["nextStepKind"] == "detail"


def test_import_documents_returns_empty_workspace() -> None:
    app, source, workspace_id = import_documents_app([])

    with TestClient(app) as client:
        response = client.get("/api/v1/imports/documents")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["pagination"]["total"] == 0
    assert source.workspace_ids == [workspace_id] * 4


def test_import_documents_rejects_inverted_statement_period() -> None:
    app, source, _ = import_documents_app([])

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/imports/documents?period_from=2026-08-01&period_to=2026-07-01"
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_period_range"
    assert source.workspace_ids == []


def test_import_documents_normalizes_unsupported_pagination_values() -> None:
    app, source, _ = import_documents_app([document_row()])

    with TestClient(app) as client:
        response = client.get("/api/v1/imports/documents?page=-4&per_page=33")

    assert response.status_code == 200
    assert source.paginations == [ImportDocumentListPagination(page=1, per_page=25)]
    assert response.json()["pagination"]["perPage"] == 25


def import_documents_app(
    rows: list[ImportDocumentListRow],
    *,
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> tuple[FastAPI, DocumentListSourceStub, UUID]:
    app = create_app()
    context = api_context(role)
    source = DocumentListSourceStub(rows)
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_import_document_list_reader] = lambda: ImportDocumentListReader(
        source
    )
    return app, source, context.workspace.workspace.id


def api_context(role: WorkspaceRole) -> ApiRequestContext:
    user_id = uuid4()
    workspace_id = uuid4()
    user = User(id=user_id, email="max@example.test", name="Max", password_hash="hash")
    workspace = Workspace(
        id=workspace_id,
        owner_id=user_id,
        name="Дом",
        type=WorkspaceType.PERSONAL,
        default_currency="RUB",
    )
    membership = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user_id,
        role=role,
        status=WorkspaceMemberStatus.ACTIVE,
    )
    return ApiRequestContext(
        workspace=WorkspaceContext(user=user, workspace=workspace, membership=membership),
        csrf_token="csrf-token",
    )


def document_row() -> ImportDocumentListRow:
    return ImportDocumentListRow(
        id=uuid4(),
        filename="statement.pdf",
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        created_at=datetime(2026, 7, 24, 10, 0, tzinfo=UTC),
        file_size_bytes=2048,
        detected_bank_name="Альфа-Банк",
        statement_period_start=date(2026, 7, 1),
        statement_period_end=date(2026, 7, 31),
        account_id=uuid4(),
        account_name="Основной",
        account_currency="RUB",
        account_bank_name="Альфа-Банк",
        total_row_count=0,
        reviewable_row_count=0,
        latest_parse_attempt_status=ParseAttemptStatus.REQUIRES_REVIEW,
    )
