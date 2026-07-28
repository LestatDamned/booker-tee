from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import app.api.v1.imports.router as imports_router_module
from api_client import ApiTestClient as TestClient
from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.imports.application.documents.upload import StatementUploadResult
from app.features.imports.errors import UploadIdempotencyConflictError
from app.features.imports.models import UploadedDocumentStatus
from app.features.users.models import User
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.service import WorkspaceContext
from app.main import create_app


def test_upload_reference_returns_active_accounts_and_limits(monkeypatch) -> None:
    context = api_context(WorkspaceRole.OWNER)
    account_id = uuid4()

    class FakeAccountService:
        def __init__(self, _session) -> None:
            pass

        async def list_active_accounts(self, workspace_id):
            assert workspace_id == context.workspace.workspace.id
            return [
                SimpleNamespace(
                    id=account_id,
                    name="Основной",
                    currency="RUB",
                    bank_name="Экспобанк",
                )
            ]

    monkeypatch.setattr(imports_router_module, "AccountService", FakeAccountService)
    app = upload_app(context)

    with TestClient(app) as client:
        response = client.get("/api/v1/imports/upload-reference")

    assert response.status_code == 200
    assert response.json() == {
        "accounts": [
            {
                "id": str(account_id),
                "name": "Основной",
                "currency": "RUB",
                "bankName": "Экспобанк",
            }
        ],
        "acceptedExtensions": [".pdf", ".xlsx"],
        "acceptedContentTypes": [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ],
        "maxFileSizeBytes": 1024,
        "canUpload": True,
    }


def test_upload_returns_committed_document_target(monkeypatch) -> None:
    context = api_context(WorkspaceRole.OWNER)
    document = SimpleNamespace(id=uuid4(), status=UploadedDocumentStatus.REQUIRES_REVIEW)
    calls: list[dict[str, object]] = []

    class FakeUploadUseCase:
        def __init__(self, _session, _settings) -> None:
            pass

        async def upload_statement(self, **kwargs):
            calls.append(kwargs)
            return StatementUploadResult(
                document=cast(Any, document),
                replayed=False,
            )

    async def fake_detail(**_kwargs):
        return SimpleNamespace(next_step="review")

    monkeypatch.setattr(imports_router_module, "StatementUploadUseCase", FakeUploadUseCase)
    monkeypatch.setattr(imports_router_module, "_read_committed_detail", fake_detail)
    app = upload_app(context)
    account_id = uuid4()
    idempotency_key = uuid4()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/imports/documents",
            data={"account_id": str(account_id)},
            files={"statement": ("statement.pdf", b"%PDF-1.4", "application/pdf")},
            headers={"Idempotency-Key": str(idempotency_key)},
        )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(document.id),
        "status": "requires_review",
        "replayed": False,
        "navigationTarget": "document_detail",
        "nextStep": "review",
    }
    assert calls[0]["account_id"] == account_id
    assert calls[0]["idempotency_key"] == idempotency_key


def test_upload_rejects_viewer_and_requires_idempotency_key(monkeypatch) -> None:
    viewer_app = upload_app(api_context(WorkspaceRole.VIEWER))
    with TestClient(viewer_app) as client:
        forbidden = client.post(
            "/api/v1/imports/documents",
            data={"account_id": str(uuid4())},
            files={"statement": ("statement.pdf", b"%PDF-1.4", "application/pdf")},
            headers={"Idempotency-Key": str(uuid4())},
        )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "import_management_forbidden"

    owner_app = upload_app(api_context(WorkspaceRole.OWNER))
    with TestClient(owner_app) as client:
        missing_key = client.post(
            "/api/v1/imports/documents",
            data={"account_id": str(uuid4())},
            files={"statement": ("statement.pdf", b"%PDF-1.4", "application/pdf")},
        )
    assert missing_key.status_code == 422
    assert "Idempotency-Key" in str(missing_key.json())


def test_upload_maps_idempotency_conflict_to_409(monkeypatch) -> None:
    class ConflictingUploadUseCase:
        def __init__(self, _session, _settings) -> None:
            pass

        async def upload_statement(self, **_kwargs):
            raise UploadIdempotencyConflictError("Ключ уже использован.")

    monkeypatch.setattr(
        imports_router_module,
        "StatementUploadUseCase",
        ConflictingUploadUseCase,
    )
    app = upload_app(api_context(WorkspaceRole.OWNER))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/imports/documents",
            data={"account_id": str(uuid4())},
            files={"statement": ("statement.pdf", b"%PDF-1.4", "application/pdf")},
            headers={"Idempotency-Key": str(uuid4())},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "upload_idempotency_conflict"


def upload_app(context: ApiRequestContext):
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_session] = lambda: object()
    app.dependency_overrides[get_settings] = lambda: Settings(statement_upload_max_bytes=1024)
    return app


def api_context(role: WorkspaceRole) -> ApiRequestContext:
    user_id = uuid4()
    workspace_id = uuid4()
    user = User(id=user_id, email="max@example.test", name="Max", password_hash="hash")
    workspace = Workspace(
        id=workspace_id,
        owner_id=user_id,
        name="Дом",
        type=WorkspaceType.PERSONAL,
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
