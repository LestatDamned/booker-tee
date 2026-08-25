from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from pdfplumber.utils.exceptions import MalformedPDFException
from pypdfium2 import PdfiumError

from api_client import ApiTestClient as TestClient
from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.core.config import get_settings
from app.db.session import get_session
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.documents.types import (
    UploadedDocumentSource,
    UploadedDocumentStatus,
    UploadedDocumentType,
)
from app.features.imports.mapping import coordinate_pdf
from app.features.imports.mapping.coordinate_dto import (
    CoordinateCapability,
    CoordinateMappingOverview,
    CoordinatePageMetadata,
)
from app.features.imports.mapping.coordinate_pdf import CoordinatePdfError
from app.features.imports.mapping.coordinate_service import (
    CoordinateMappingImportService,
    CoordinateMappingService,
)
from app.features.imports.mapping.dto import StatementMappingImportResult
from app.features.imports.mapping.errors import MappingImportUnavailableError
from app.features.users.models import User
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.service import WorkspaceContext


def test_coordinate_overview_api_returns_workspace_safe_projection(
    app: FastAPI, monkeypatch
) -> None:
    context = _context()
    document_id = uuid4()

    async def overview(self, **kwargs):
        assert kwargs["workspace_id"] == context.workspace.workspace.id
        return CoordinateMappingOverview(
            document_id=document_id,
            filename="sanitized.pdf",
            page_count=1,
            pages=(
                CoordinatePageMetadata(
                    page_number=1,
                    width=600,
                    height=800,
                    aspect_ratio=0.75,
                    has_text_layer=True,
                ),
            ),
            default_currency="RUB",
            capability=CoordinateCapability(allowed=True, blocking_reason_codes=()),
            templates=(),
        )

    monkeypatch.setattr(CoordinateMappingService, "overview", overview)
    _override(app, context)
    with TestClient(app) as client:
        response = client.get(f"/api/v1/imports/documents/{document_id}/coordinate-mapping")

    assert response.status_code == 200
    assert response.json()["pages"][0] == {
        "pageNumber": 1,
        "width": 600.0,
        "height": 800.0,
        "aspectRatio": 0.75,
        "hasTextLayer": True,
    }
    assert "storage" not in str(response.json()).casefold()
    assert "path" not in str(response.json()).casefold()


def test_coordinate_page_image_is_png_private_and_no_store(app: FastAPI, monkeypatch) -> None:
    context = _context()
    document_id = uuid4()

    async def render_page(self, **kwargs):
        assert kwargs["page_number"] == 1
        return b"\x89PNG\r\n\x1a\n"

    monkeypatch.setattr(CoordinateMappingService, "render_page", render_page)
    _override(app, context)
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/imports/documents/{document_id}/coordinate-mapping/pages/1/image"
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, no-store"


def test_coordinate_page_image_openapi_declares_png(
    canonical_openapi_schema: dict[str, Any],
) -> None:
    paths = canonical_openapi_schema["paths"]
    operation = paths[
        "/api/v1/imports/documents/{document_id}/coordinate-mapping/pages/{page_number}/image"
    ]["get"]
    assert "image/png" in operation["responses"]["200"]["content"]


def test_coordinate_preview_rejects_extra_browser_payload(app: FastAPI) -> None:
    context = _context()
    document_id = uuid4()
    _override(app, context)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/imports/documents/{document_id}/coordinate-mapping/preview",
            headers={"X-CSRF-Token": context.csrf_token},
            json={
                "spec": _spec_payload(),
                "previewRows": [{"amount": "trusted-client-value"}],
            },
        )

    assert response.status_code == 422


@pytest.mark.parametrize("currency", ["", "TOOLONG"])
def test_coordinate_import_rejects_invalid_currency_without_mutation(
    app: FastAPI, monkeypatch, currency: str
) -> None:
    async def unexpected_import(self, **kwargs):
        raise AssertionError("invalid currency reached persistence")

    monkeypatch.setattr(
        CoordinateMappingImportService,
        "import_rows_idempotently",
        unexpected_import,
    )
    context = _context()
    payload = _spec_payload()
    payload["defaultCurrency"] = currency
    _override(app, context)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/imports/documents/{uuid4()}/coordinate-mapping/import",
            headers={
                "X-CSRF-Token": context.csrf_token,
                "Idempotency-Key": str(uuid4()),
            },
            json={"spec": payload, "templateName": "Must not persist"},
        )

    assert response.status_code == 422


def test_coordinate_import_requires_import_management_permission(app: FastAPI, monkeypatch) -> None:
    async def unexpected_import(self, **kwargs):
        raise AssertionError("viewer reached coordinate persistence")

    monkeypatch.setattr(
        CoordinateMappingImportService,
        "import_rows_idempotently",
        unexpected_import,
    )
    context = _context(role=WorkspaceRole.VIEWER)
    _override(app, context)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/imports/documents/{uuid4()}/coordinate-mapping/import",
            headers={
                "X-CSRF-Token": context.csrf_token,
                "Idempotency-Key": str(uuid4()),
            },
            json={"spec": _spec_payload(), "templateName": None},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "import_management_forbidden"


def test_coordinate_import_returns_review_target(app: FastAPI, monkeypatch) -> None:
    context = _context()
    document_id = uuid4()

    async def imported(self, **kwargs):
        assert kwargs["workspace_id"] == context.workspace.workspace.id
        return StatementMappingImportResult(
            document_id=document_id,
            document_status=UploadedDocumentStatus.REQUIRES_REVIEW,
            imported_row_count=2,
            template_id=None,
            replayed=False,
        )

    monkeypatch.setattr(
        CoordinateMappingImportService,
        "import_rows_idempotently",
        imported,
    )
    _override(app, context)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/imports/documents/{document_id}/coordinate-mapping/import",
            headers={
                "X-CSRF-Token": context.csrf_token,
                "Idempotency-Key": str(uuid4()),
            },
            json={"spec": _spec_payload(), "templateName": None},
        )

    assert response.status_code == 200
    assert response.json()["reviewTarget"] == {
        "kind": "import_review",
        "documentId": str(document_id),
    }


@pytest.mark.parametrize(
    "error",
    [
        CoordinatePdfError("PDF page was not found."),
        MappingImportUnavailableError("source_missing"),
    ],
)
def test_coordinate_page_errors_are_controlled(app: FastAPI, monkeypatch, error) -> None:
    async def failed_page(self, **kwargs):
        raise error

    monkeypatch.setattr(CoordinateMappingService, "render_page", failed_page)
    context = _context()
    _override(app, context)
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/imports/documents/{uuid4()}/coordinate-mapping/pages/99/image"
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "coordinate_mapping_unavailable"


@pytest.mark.parametrize("renderer_error", [MalformedPDFException, PdfiumError])
def test_coordinate_renderer_failure_is_controlled_without_path_leak(
    app: FastAPI, monkeypatch, tmp_path: Path, renderer_error
) -> None:
    context = _context()
    document_id = uuid4()
    sensitive_path = "/private/statements/customer.pdf"
    (tmp_path / "statement.pdf").touch()
    document = SimpleNamespace(
        id=document_id,
        workspace_id=context.workspace.workspace.id,
        content_type="application/pdf",
        document_type=UploadedDocumentType.BANK_STATEMENT,
        source=UploadedDocumentSource.WEB_UPLOAD,
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        storage_key="statement.pdf",
        account_id=uuid4(),
        raw_transactions=[],
        parse_attempts=[
            SimpleNamespace(
                started_at=datetime.now(UTC),
                validation_report_json={
                    "status": "valid",
                    "source": "visual_coordinate_mapping",
                },
            )
        ],
    )

    async def get_document(self, workspace_id, requested_document_id):
        assert workspace_id == context.workspace.workspace.id
        assert requested_document_id == document_id
        return document

    page = SimpleNamespace(
        width=600,
        height=800,
        to_image=lambda **_kwargs: (_ for _ in ()).throw(renderer_error(sensitive_path)),
    )

    class Pdf:
        pages = [page]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(DocumentRepository, "get_document_for_workspace", get_document)
    monkeypatch.setattr(coordinate_pdf.pdfplumber, "open", lambda _path: Pdf())
    _override(app, context)
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(upload_storage_dir=tmp_path)
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/imports/documents/{document_id}/coordinate-mapping/pages/1/image"
        )

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "coordinate_mapping_unavailable",
        "message": "Source PDF could not be read.",
    }
    assert sensitive_path not in response.text


@pytest.mark.parametrize("endpoint", ["preview", "import"])
def test_coordinate_pdf_failure_is_controlled_for_preview_and_import(
    app: FastAPI, monkeypatch, endpoint: str
) -> None:
    async def failed(self, **kwargs):
        raise CoordinatePdfError("Source PDF could not be read.")

    service = CoordinateMappingService if endpoint == "preview" else CoordinateMappingImportService
    method = "preview" if endpoint == "preview" else "import_rows_idempotently"
    monkeypatch.setattr(service, method, failed)
    context = _context()
    _override(app, context)
    headers = {"X-CSRF-Token": context.csrf_token}
    if endpoint == "import":
        headers["Idempotency-Key"] = str(uuid4())
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/imports/documents/{uuid4()}/coordinate-mapping/{endpoint}",
            headers=headers,
            json={
                "spec": _spec_payload(),
                **({"templateName": None} if endpoint == "import" else {}),
            },
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "coordinate_mapping_unavailable"


def _spec_payload() -> dict[str, object]:
    return {
        "version": 1,
        "defaultCurrency": "RUB",
        "unsignedAmountDirection": "require_sign",
        "layouts": {
            "first": {
                "pageAspectRatio": 0.75,
                "transactionTop": 0.1,
                "transactionBottom": 0.9,
                "sampleRow": {"x0": 0.05, "y0": 0.2, "x1": 0.95, "y1": 0.3},
                "fields": {
                    "operation_date": {"x0": 0.05, "y0": 0.2, "x1": 0.2, "y1": 0.3},
                    "description": {"x0": 0.25, "y0": 0.2, "x1": 0.65, "y1": 0.3},
                    "amount": {"x0": 0.75, "y0": 0.2, "x1": 0.95, "y1": 0.3},
                },
            }
        },
    }


def _override(app: FastAPI, context: ApiRequestContext) -> None:
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_session] = lambda: SimpleNamespace()
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
        upload_storage_dir=Path("/tmp/not-read-by-api-stub")
    )


def _context(role: WorkspaceRole = WorkspaceRole.OWNER) -> ApiRequestContext:
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
