from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.v1.imports.dependencies import get_import_document_detail_reader
from app.core.config import get_settings
from app.db.session import get_session
from app.features.imports.application.documents.detail_reading import (
    ImportDocumentDetailReader,
)
from app.features.imports.application.documents.snapshot import (
    ImportDocumentSnapshot,
    ImportRawTransactionRow,
)
from app.features.imports.models import RawTransactionStatus, UploadedDocumentStatus
from app.features.users.models import User
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.service import WorkspaceContext
from app.main import create_app


class DetailReaderStub:
    def __init__(self, detail: ImportDocumentSnapshot | None) -> None:
        self.detail = detail
        self.workspace_ids: list[UUID] = []

    async def read(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        can_manage: bool,
    ):
        self.workspace_ids.append(workspace_id)
        if self.detail is None or self.detail.id != document_id:
            return None
        return ImportDocumentDetailReader.from_snapshot(
            self.detail,
            can_manage=can_manage,
        )


def test_import_document_detail_returns_bounded_safe_projection() -> None:
    context = api_context(WorkspaceRole.OWNER)
    detail = document_snapshot()
    reader = DetailReaderStub(detail)
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_import_document_detail_reader] = lambda: cast(Any, reader)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/imports/documents/{detail.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["account"] is None
    assert payload["nextStep"] == "review"
    assert payload["rawRows"]["total"] == 1
    assert payload["rawRows"]["items"][0]["amount"] == "-125.50"
    assert payload["validation"]["reasonCode"] == "totals_match"
    assert payload["validation"]["ignoredRowCount"] == 0
    assert payload["capabilities"]["delete"]["allowed"] is True
    assert "storageKey" not in payload
    assert "sha256Hash" not in payload
    assert "rawTables" not in str(payload)
    assert reader.workspace_ids == [context.workspace.workspace.id]


def test_import_document_detail_masks_other_workspace_as_not_found() -> None:
    context = api_context(WorkspaceRole.OWNER)
    reader = DetailReaderStub(None)
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_import_document_detail_reader] = lambda: cast(Any, reader)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/imports/documents/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "import_document_not_found"


def test_import_document_detail_viewer_keeps_data_but_loses_management() -> None:
    context = api_context(WorkspaceRole.VIEWER)
    detail = document_snapshot()
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_import_document_detail_reader] = lambda: cast(
        Any, DetailReaderStub(detail)
    )

    with TestClient(app) as client:
        response = client.get(f"/api/v1/imports/documents/{detail.id}")

    assert response.status_code == 200
    assert response.json()["rawRows"]["total"] == 1
    capabilities = response.json()["capabilities"]
    assert capabilities["canManage"] is False
    assert capabilities["delete"]["blockingReasonCodes"] == ["import_management_forbidden"]


def test_document_mutation_is_forbidden_for_viewer_before_use_case() -> None:
    context = api_context(WorkspaceRole.VIEWER)
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_session] = lambda: cast(Any, object())
    app.dependency_overrides[get_settings] = lambda: cast(
        Any,
        SimpleNamespace(),
    )

    with TestClient(app) as client:
        response = client.request(
            "DELETE",
            f"/api/v1/imports/documents/{uuid4()}",
            json={"expectedStatus": "requires_review"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "import_management_forbidden"


def document_snapshot() -> ImportDocumentSnapshot:
    return ImportDocumentSnapshot(
        id=uuid4(),
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        original_filename="statement.pdf",
        sha256_hash="a" * 64,
        storage_key="private/storage.pdf",
        bank_name="Альфа-Банк",
        statement_type="account_statement",
        account=None,
        validation={"status": "valid", "extracted_count": 1},
        raw_transactions=[
            ImportRawTransactionRow(
                row_index=1,
                status=RawTransactionStatus.NORMALIZED,
                parse_attempt_id=uuid4(),
                display_date=date(2026, 7, 15),
                amount=Decimal("-125.50"),
                amount_raw="-125.50",
                currency="RUB",
                description="Покупка",
                normalization_error="",
            )
        ],
        parse_attempts=[],
        statement_period_start=date(2026, 7, 1),
        statement_period_end=date(2026, 7, 31),
        file_size_bytes=2048,
        created_at=datetime(2026, 7, 24, 10, tzinfo=UTC),
        updated_at=datetime(2026, 7, 24, 10, tzinfo=UTC),
    )


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
        workspace=WorkspaceContext(
            user=user,
            workspace=workspace,
            membership=membership,
        ),
        csrf_token="csrf-token",
    )
