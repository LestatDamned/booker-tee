from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.mapping.commands.import_rows import (
    StatementMappingImportService,
)
from app.features.imports.mapping.dto import (
    MappingTemplateSnapshot,
    StatementMappingSpec,
    UnsignedAmountDirection,
)
from app.features.imports.mapping.errors import MappingImportIdempotencyConflictError


class MappingImportsStub:
    def __init__(self, document: object) -> None:
        self.document = document
        self.execution = None
        self.created_templates: list[Any] = []

    async def get_document_for_workspace_for_update(self, *_args):
        return self.document

    async def get_document_for_workspace(self, *_args):
        return self.document

    async def get_mapping_execution(self, **_kwargs):
        return self.execution

    async def create_mapping_execution(self, execution):
        self.execution = execution
        return execution

    async def create_mapping_template(
        self,
        *,
        workspace_id: UUID,
        name: str,
        bank_name: str | None,
        statement_type: str | None,
        mapping: StatementMappingSpec,
        table_signature: dict[str, object] | None,
    ) -> MappingTemplateSnapshot:
        template = SimpleNamespace(
            name=name,
            bank_name=bank_name,
            statement_type=statement_type,
            mapping=mapping,
            table_signature=table_signature,
        )
        self.created_templates.append(template)
        return MappingTemplateSnapshot(
            id=uuid4(),
            name=template.name,
            bank_name=template.bank_name,
            statement_type=template.statement_type,
            default_currency=template.mapping.default_currency,
            mapping=template.mapping,
            table_signature=template.table_signature,
        )


class SessionStub:
    def __init__(self) -> None:
        self.commit_count = 0

    async def commit(self) -> None:
        self.commit_count += 1


async def test_mapping_import_replays_rows_and_template_once() -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    document = mapping_document(workspace_id, document_id)
    imports = MappingImportsStub(document)
    session = SessionStub()
    service = object.__new__(StatementMappingImportService)
    service.session = cast(Any, session)
    service.documents = cast(Any, imports)
    service.mappings = cast(Any, imports)
    create_rows = AsyncMock(return_value=[SimpleNamespace(), SimpleNamespace()])
    service.row_importer = SimpleNamespace(replace_rows=create_rows)
    idempotency_key = uuid4()
    command = mapping_command()

    first = await service.import_rows_idempotently(
        workspace_id=workspace_id,
        document_id=document_id,
        spec=command,
        idempotency_key=idempotency_key,
        template_name="  Моя   выписка  ",
    )
    replay = await service.import_rows_idempotently(
        workspace_id=workspace_id,
        document_id=document_id,
        spec=command,
        idempotency_key=idempotency_key,
        template_name="Моя выписка",
    )

    assert first.replayed is False
    assert replay.replayed is True
    assert first.imported_row_count == replay.imported_row_count == 2
    assert first.template_id == replay.template_id
    assert len(imports.created_templates) == 1
    assert imports.created_templates[0].name == "Моя выписка"
    assert create_rows.await_count == 1
    assert session.commit_count == 1


async def test_mapping_import_rejects_same_key_with_changed_payload() -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    imports = MappingImportsStub(mapping_document(workspace_id, document_id))
    session = SessionStub()
    service = object.__new__(StatementMappingImportService)
    service.session = cast(Any, session)
    service.documents = cast(Any, imports)
    service.mappings = cast(Any, imports)
    service.row_importer = SimpleNamespace(replace_rows=AsyncMock(return_value=[SimpleNamespace()]))
    idempotency_key = uuid4()

    await service.import_rows_idempotently(
        workspace_id=workspace_id,
        document_id=document_id,
        spec=mapping_command(),
        idempotency_key=idempotency_key,
    )
    changed = mapping_command().model_copy(update={"default_currency": "USD"})

    with pytest.raises(MappingImportIdempotencyConflictError):
        await service.import_rows_idempotently(
            workspace_id=workspace_id,
            document_id=document_id,
            spec=changed,
            idempotency_key=idempotency_key,
        )

    assert session.commit_count == 1


def mapping_document(workspace_id: UUID, document_id: UUID):
    return SimpleNamespace(
        id=document_id,
        workspace_id=workspace_id,
        account_id=uuid4(),
        bank_name="Тест Банк",
        statement_type="card_statement",
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        raw_transactions=[],
        parse_attempts=[
            SimpleNamespace(
                id=uuid4(),
                started_at=datetime.now(UTC),
                raw_tables_json=[
                    {
                        "page_number": 1,
                        "tables": [
                            [
                                ["Дата", "Описание", "Сумма"],
                                ["24.07.2026", "Кофе", "-250,00"],
                            ]
                        ],
                    }
                ],
            )
        ],
    )


def mapping_command() -> StatementMappingSpec:
    return StatementMappingSpec(
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
