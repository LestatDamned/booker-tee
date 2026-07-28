from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.v1.imports.dependencies import (
    get_unknown_statement_mapping_importer,
    get_unknown_statement_mapping_reader,
)
from app.features.imports.application.unknown_statement_mappings.dto import (
    StatementMappingSpec,
    UnknownStatementMappingWarning,
    UnsignedAmountDirection,
)
from app.features.imports.application.unknown_statement_mappings.mapping_defaults import (
    MappingDefaultSource,
)
from app.features.imports.application.unknown_statement_mappings.read_models import (
    MappingAccountDto,
    MappingCapabilityDto,
    MappingSourceRowDto,
    MappingSourceRowsDto,
    MappingTableRefDto,
    UnknownStatementMappingPreviewResult,
    UnknownStatementMappingReadModel,
)
from app.features.imports.application.unknown_statement_mappings.validation import (
    MappingCommandValidationError,
    MappingValidationCode,
    MappingValidationIssue,
    MappingValidationSeverity,
)
from app.features.imports.errors import MappingImportIdempotencyConflictError
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


class MappingReaderStub:
    def __init__(
        self,
        mapping: UnknownStatementMappingReadModel | None,
        *,
        validation_error: MappingCommandValidationError | None = None,
    ) -> None:
        self.mapping = mapping
        self.validation_error = validation_error
        self.read_calls: list[dict[str, object]] = []
        self.preview_calls: list[dict[str, object]] = []
        self.source_rows_calls: list[dict[str, object]] = []

    async def read(self, **kwargs):
        self.read_calls.append(kwargs)
        return self.mapping

    async def preview(self, **kwargs):
        self.preview_calls.append(kwargs)
        if self.validation_error is not None:
            raise self.validation_error
        if self.mapping is None:
            return None
        return UnknownStatementMappingPreviewResult(
            rows=(),
            total_row_count=24,
            valid_row_count=23,
            invalid_row_count=1,
            row_limit=20,
            rows_truncated=True,
            compatible_tables=(MappingTableRefDto(1, 0), MappingTableRefDto(2, 0)),
            warnings=(
                UnknownStatementMappingWarning(
                    code="unsigned_amount_direction_required",
                    severity="warning",
                    fields=["unsigned_amount_direction"],
                    affected_row_count=7,
                ),
            ),
            can_import=True,
        )

    async def source_rows(self, **kwargs):
        self.source_rows_calls.append(kwargs)
        if self.mapping is None:
            return None
        return MappingSourceRowsDto(
            table_ref=MappingTableRefDto(
                cast(int, kwargs["page_number"]),
                cast(int, kwargs["table_index"]),
            ),
            rows=(MappingSourceRowDto(row_number=31, cells=("31.07.2026", "Операция")),),
            total_row_count=80,
            start_row_number=31,
            row_limit=30,
            has_previous=True,
            has_next=True,
        )


class MappingImporterStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.error: Exception | None = None

    async def import_mapped_rows_idempotently(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        document_id = cast(UUID, kwargs["document_id"])
        return SimpleNamespace(
            document=SimpleNamespace(
                id=document_id,
                status=UploadedDocumentStatus.REQUIRES_REVIEW,
            ),
            imported_row_count=24,
            template_id=uuid4() if kwargs["template_name"] else None,
            replayed=False,
        )


def test_mapping_read_api_returns_typed_safe_projection() -> None:
    context = api_context(WorkspaceRole.OWNER)
    mapping = mapping_read_model()
    reader = MappingReaderStub(mapping)
    app = mapping_app(context, reader)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/imports/documents/{mapping.document_id}/mapping")

    assert response.status_code == 200
    payload = response.json()
    assert payload["documentId"] == str(mapping.document_id)
    assert payload["account"]["name"] == "Основной"
    assert payload["defaultMapping"]["tableRef"] == {
        "pageNumber": 1,
        "tableIndex": 0,
    }
    assert payload["defaultMapping"]["firstDataRowNumber"] == 2
    assert payload["capability"] == {
        "allowed": True,
        "blockingReasonCodes": [],
    }
    assert "storageKey" not in str(payload)
    assert reader.read_calls[0]["workspace_id"] == context.workspace.workspace.id


def test_mapping_preview_api_converts_visible_row_number_and_returns_scope() -> None:
    context = api_context(WorkspaceRole.OWNER)
    mapping = mapping_read_model()
    reader = MappingReaderStub(mapping)
    app = mapping_app(context, reader)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/imports/documents/{mapping.document_id}/mapping/preview",
            json={
                "mapping": {
                    "tableRef": {"pageNumber": 1, "tableIndex": 0},
                    "operationDateColumn": 0,
                    "descriptionColumn": 1,
                    "amountColumn": 2,
                    "firstDataRowNumber": 2,
                    "defaultCurrency": "rub",
                    "unsignedAmountDirection": "require_sign",
                }
            },
        )

    assert response.status_code == 200
    command = cast(StatementMappingSpec, reader.preview_calls[0]["spec"])
    assert command.first_data_row == 1
    assert command.default_currency == "RUB"
    payload = response.json()
    assert payload["totalRowCount"] == 24
    assert payload["rowLimit"] == 20
    assert payload["rowsTruncated"] is True
    assert payload["compatibleTables"] == [
        {"pageNumber": 1, "tableIndex": 0},
        {"pageNumber": 2, "tableIndex": 0},
    ]
    assert payload["warnings"] == [
        {
            "code": "unsigned_amount_direction_required",
            "severity": "warning",
            "fields": ["unsignedAmountDirection"],
            "affectedRowCount": 7,
        }
    ]


def test_mapping_source_rows_api_returns_bounded_workspace_projection() -> None:
    context = api_context(WorkspaceRole.OWNER)
    mapping = mapping_read_model()
    reader = MappingReaderStub(mapping)
    app = mapping_app(context, reader)

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/imports/documents/{mapping.document_id}/mapping/"
            "tables/2/0/rows?startRowNumber=31&rowLimit=30"
        )

    assert response.status_code == 200
    assert response.json() == {
        "tableRef": {"pageNumber": 2, "tableIndex": 0},
        "rows": [{"rowNumber": 31, "cells": ["31.07.2026", "Операция"]}],
        "totalRowCount": 80,
        "startRowNumber": 31,
        "rowLimit": 30,
        "hasPrevious": True,
        "hasNext": True,
    }
    assert reader.source_rows_calls == [
        {
            "workspace_id": context.workspace.workspace.id,
            "document_id": mapping.document_id,
            "page_number": 2,
            "table_index": 0,
            "start_row_number": 31,
            "row_limit": 30,
        }
    ]


def test_mapping_preview_api_returns_stable_field_errors() -> None:
    context = api_context(WorkspaceRole.OWNER)
    mapping = mapping_read_model()
    error = MappingCommandValidationError(
        (
            MappingValidationIssue(
                code=MappingValidationCode.DUPLICATE_ROLES,
                severity=MappingValidationSeverity.ERROR,
                message="Одна колонка не может использоваться для нескольких ролей.",
                fields=("operationDateColumn", "descriptionColumn"),
            ),
            MappingValidationIssue(
                code=MappingValidationCode.CONFLICTING_AMOUNT,
                severity=MappingValidationSeverity.ERROR,
                message="Выберите единую сумму или отдельные списание и зачисление.",
                fields=("amountColumn", "debitAmountColumn", "creditAmountColumn"),
            ),
        )
    )
    app = mapping_app(context, MappingReaderStub(mapping, validation_error=error))

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/imports/documents/{mapping.document_id}/mapping/preview",
            json={
                "mapping": {
                    "tableRef": {"pageNumber": 1, "tableIndex": 0},
                    "operationDateColumn": 0,
                    "descriptionColumn": 0,
                    "amountColumn": 2,
                    "firstDataRowNumber": 2,
                    "defaultCurrency": "RUB",
                    "unsignedAmountDirection": "require_sign",
                }
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "mapping_validation_failed"
    assert set(response.json()["error"]["fieldErrors"]) == {
        "operationDateColumn",
        "descriptionColumn",
        "amountColumn",
        "debitAmountColumn",
        "creditAmountColumn",
    }


def test_mapping_api_requires_management_and_masks_other_workspace() -> None:
    mapping = mapping_read_model()
    viewer_context = api_context(WorkspaceRole.VIEWER)
    viewer_reader = MappingReaderStub(mapping)
    viewer_app = mapping_app(viewer_context, viewer_reader)

    with TestClient(viewer_app) as client:
        forbidden = client.get(f"/api/v1/imports/documents/{mapping.document_id}/mapping")

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "import_management_forbidden"
    assert viewer_reader.read_calls == []

    owner_context = api_context(WorkspaceRole.OWNER)
    missing_app = mapping_app(owner_context, MappingReaderStub(None))
    with TestClient(missing_app) as client:
        missing = client.get(f"/api/v1/imports/documents/{uuid4()}/mapping")

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "import_document_not_found"


def test_mapping_import_uses_idempotency_and_returns_review_target() -> None:
    context = api_context(WorkspaceRole.OWNER)
    mapping = mapping_read_model()
    importer = MappingImporterStub()
    app = mapping_app(context, MappingReaderStub(mapping), importer)
    idempotency_key = uuid4()

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/imports/documents/{mapping.document_id}/mapping/import",
            headers={"Idempotency-Key": str(idempotency_key)},
            json={
                "mapping": {
                    "tableRef": {"pageNumber": 1, "tableIndex": 0},
                    "operationDateColumn": 0,
                    "descriptionColumn": 1,
                    "amountColumn": 2,
                    "firstDataRowNumber": 2,
                    "defaultCurrency": "RUB",
                    "unsignedAmountDirection": "expense",
                },
                "templateName": "  Экспобанк карта  ",
            },
        )

    assert response.status_code == 200
    assert importer.calls[0]["idempotency_key"] == idempotency_key
    assert importer.calls[0]["template_name"] == "  Экспобанк карта  "
    assert response.json() == {
        "documentId": str(mapping.document_id),
        "status": "requires_review",
        "importedRowCount": 24,
        "templateId": response.json()["templateId"],
        "replayed": False,
        "reviewTarget": {
            "kind": "import_review",
            "documentId": str(mapping.document_id),
        },
    }


def test_mapping_import_requires_key_and_maps_payload_conflict() -> None:
    context = api_context(WorkspaceRole.OWNER)
    mapping = mapping_read_model()
    importer = MappingImporterStub()
    app = mapping_app(context, MappingReaderStub(mapping), importer)
    payload = {
        "mapping": {
            "tableRef": {"pageNumber": 1, "tableIndex": 0},
            "operationDateColumn": 0,
            "descriptionColumn": 1,
            "amountColumn": 2,
            "firstDataRowNumber": 2,
            "defaultCurrency": "RUB",
            "unsignedAmountDirection": "require_sign",
        }
    }

    with TestClient(app) as client:
        missing_key = client.post(
            f"/api/v1/imports/documents/{mapping.document_id}/mapping/import",
            json=payload,
        )

        importer.error = MappingImportIdempotencyConflictError("Ключ уже использован.")
        conflict = client.post(
            f"/api/v1/imports/documents/{mapping.document_id}/mapping/import",
            headers={"Idempotency-Key": str(uuid4())},
            json=payload,
        )

    assert missing_key.status_code == 422
    assert "Idempotency-Key" in str(missing_key.json())
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "mapping_import_idempotency_conflict"


def mapping_read_model() -> UnknownStatementMappingReadModel:
    command = StatementMappingSpec(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=1,
        amount_column=2,
        currency_column=None,
        first_data_row=1,
        default_currency="RUB",
        unsigned_amount_direction=UnsignedAmountDirection.REQUIRE_SIGN,
    )
    return UnknownStatementMappingReadModel(
        document_id=uuid4(),
        filename="statement.xlsx",
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        bank_name="Unknown Bank",
        statement_type="account_statement",
        account=MappingAccountDto(id=uuid4(), name="Основной", currency="RUB"),
        default_currency="RUB",
        capability=MappingCapabilityDto(allowed=True, blocking_reason_codes=()),
        default_mapping=command,
        default_source=MappingDefaultSource.ANALYZER,
        selected_template_id=None,
        templates=(),
        tables=(),
        total_table_count=0,
        tables_truncated=False,
    )


def mapping_app(
    context: ApiRequestContext,
    reader: MappingReaderStub,
    importer: MappingImporterStub | None = None,
):
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_unknown_statement_mapping_reader] = lambda: cast(
        Any,
        reader,
    )
    if importer is not None:
        app.dependency_overrides[get_unknown_statement_mapping_importer] = lambda: cast(
            Any,
            importer,
        )
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
