import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI

import app.api.v1.imports.router as imports_router_module
from api_client import ApiTestClient as TestClient
from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.imports.documents.commands.upload import (
    StatementUploadResult,
    StatementUploadUseCase,
)
from app.features.imports.documents.errors import (
    UploadAccountNotFoundError,
    UploadIdempotencyConflictError,
    UploadProcessingError,
)
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.documents.storage import UploadStorage
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.users.models import User
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.service import WorkspaceContext


def test_upload_reference_returns_active_accounts_and_limits(
    app: FastAPI,
    monkeypatch,
) -> None:
    context = api_context(WorkspaceRole.OWNER)
    account_id = uuid4()

    class FakeAccountResolver:
        def __init__(self, _session) -> None:
            pass

        async def list_manual_accounts(self, workspace_id):
            assert workspace_id == context.workspace.workspace.id
            return [
                SimpleNamespace(
                    id=account_id,
                    name="Основной",
                    currency="RUB",
                    bank_name="Экспобанк",
                )
            ]

    monkeypatch.setattr(
        imports_router_module,
        "LedgerReferenceResolver",
        FakeAccountResolver,
    )
    app = upload_app(app, context)

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


def test_upload_returns_committed_document_target(app: FastAPI, monkeypatch) -> None:
    context = api_context(WorkspaceRole.OWNER)
    document = SimpleNamespace(id=uuid4(), status=UploadedDocumentStatus.REQUIRES_REVIEW)
    calls: list[dict[str, object]] = []

    class FakeUploadUseCase:
        def __init__(self, _session, _settings) -> None:
            pass

        async def upload_statement(self, **kwargs):
            calls.append(kwargs)
            return StatementUploadResult(
                document_id=document.id,
                document_status=document.status,
                filename="statement.pdf",
                replayed=False,
            )

    async def fake_detail(**_kwargs):
        return SimpleNamespace(next_step="review")

    monkeypatch.setattr(imports_router_module, "StatementUploadUseCase", FakeUploadUseCase)
    monkeypatch.setattr(imports_router_module, "_read_committed_detail", fake_detail)
    app = upload_app(app, context)
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


def test_upload_masks_unexpected_processing_failure_from_response_and_logs(
    app: FastAPI,
    monkeypatch,
    caplog,
) -> None:
    marker = "RAW_FINANCIAL_MARKER /private/statement.pdf"

    class FakeUploadUseCase:
        def __init__(self, _session, _settings) -> None:
            pass

        async def upload_statement(self, **_kwargs):
            try:
                raise RuntimeError(marker)
            except RuntimeError:
                raise UploadProcessingError("Statement processing failed.") from None

    monkeypatch.setattr(imports_router_module, "StatementUploadUseCase", FakeUploadUseCase)
    app = upload_app(app, api_context(WorkspaceRole.OWNER))
    caplog.set_level(logging.ERROR)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/imports/documents",
            data={"account_id": str(uuid4())},
            files={"statement": ("statement.pdf", b"%PDF-1.4", "application/pdf")},
            headers={"Idempotency-Key": str(uuid4())},
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "statement_processing_failed"
    assert marker not in response.text
    assert marker not in caplog.text


def test_real_upload_use_case_masks_pre_attempt_failure_from_api_and_logs(
    app: FastAPI,
    monkeypatch,
    caplog,
) -> None:
    marker = "PRE_ATTEMPT_DB_MARKER /private/upload/source.pdf sql-params"
    context = api_context(WorkspaceRole.OWNER)
    account_id = uuid4()
    session = SimpleNamespace(rollback=AsyncMock(), commit=AsyncMock())
    monkeypatch.setattr(
        LedgerReferenceResolver,
        "get_import_account",
        AsyncMock(return_value=SimpleNamespace(id=account_id, currency="RUB")),
    )
    monkeypatch.setattr(
        DocumentRepository,
        "get_document_for_workspace",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        UploadStorage,
        "save_upload",
        AsyncMock(side_effect=RuntimeError(marker)),
    )
    assert imports_router_module.StatementUploadUseCase is StatementUploadUseCase
    app = upload_app(app, context)
    app.dependency_overrides[get_session] = lambda: session
    caplog.set_level(logging.ERROR)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/imports/documents",
            data={"account_id": str(account_id)},
            files={"statement": ("statement.pdf", b"%PDF-1.4", "application/pdf")},
            headers={"Idempotency-Key": str(uuid4())},
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "statement_processing_failed"
    assert marker not in response.text
    assert marker not in caplog.text
    session.rollback.assert_awaited_once()


def test_upload_rejects_viewer(app: FastAPI) -> None:
    app = upload_app(app, api_context(WorkspaceRole.VIEWER))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/imports/documents",
            data={"account_id": str(uuid4())},
            files={"statement": ("statement.pdf", b"%PDF-1.4", "application/pdf")},
            headers={"Idempotency-Key": str(uuid4())},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "import_management_forbidden"


def test_upload_requires_idempotency_key(app: FastAPI) -> None:
    app = upload_app(app, api_context(WorkspaceRole.OWNER))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/imports/documents",
            data={"account_id": str(uuid4())},
            files={"statement": ("statement.pdf", b"%PDF-1.4", "application/pdf")},
        )

    assert response.status_code == 422
    assert "Idempotency-Key" in str(response.json())


def test_upload_maps_idempotency_conflict_to_409(app: FastAPI, monkeypatch) -> None:
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
    app = upload_app(app, api_context(WorkspaceRole.OWNER))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/imports/documents",
            data={"account_id": str(uuid4())},
            files={"statement": ("statement.pdf", b"%PDF-1.4", "application/pdf")},
            headers={"Idempotency-Key": str(uuid4())},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "upload_idempotency_conflict"


def test_upload_masks_unavailable_account_as_not_found(app: FastAPI, monkeypatch) -> None:
    class UnavailableAccountUploadUseCase:
        def __init__(self, _session, _settings) -> None:
            pass

        async def upload_statement(self, **_kwargs):
            raise UploadAccountNotFoundError("Выбранный счёт недоступен в текущем пространстве.")

    monkeypatch.setattr(
        imports_router_module,
        "StatementUploadUseCase",
        UnavailableAccountUploadUseCase,
    )
    app = upload_app(app, api_context(WorkspaceRole.OWNER))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/imports/documents",
            data={"account_id": str(uuid4())},
            files={"statement": ("statement.pdf", b"%PDF-1.4", "application/pdf")},
            headers={"Idempotency-Key": str(uuid4())},
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "upload_account_not_found"


def upload_app(app: FastAPI, context: ApiRequestContext) -> FastAPI:
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
