from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.mapping.coordinate_dto import (
    CoordinateMappingSpec,
    CoordinateTemplateSnapshot,
)
from app.features.imports.mapping.dto import (
    MappingTemplateSnapshot,
    StatementMappingSpec,
)
from app.features.imports.models import (
    ImportMappingExecution,
    ImportMappingTemplate,
)


class MappingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
        column_mapping = mapping.model_dump(mode="json")
        if table_signature is not None:
            column_mapping["table_signature"] = table_signature
        model = ImportMappingTemplate(
            workspace_id=workspace_id,
            name=name,
            bank_name=bank_name,
            statement_type=statement_type,
            default_currency=mapping.default_currency,
            column_mapping_json=column_mapping,
        )
        self.session.add(model)
        await self.session.flush()
        return _template_snapshot(model)

    async def create_mapping_execution(
        self,
        execution: ImportMappingExecution,
    ) -> ImportMappingExecution:
        self.session.add(execution)
        await self.session.flush()
        return execution

    async def get_mapping_execution(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        idempotency_key: UUID,
    ) -> ImportMappingExecution | None:
        result = await self.session.execute(
            select(ImportMappingExecution).where(
                ImportMappingExecution.workspace_id == workspace_id,
                ImportMappingExecution.uploaded_document_id == document_id,
                ImportMappingExecution.idempotency_key == str(idempotency_key),
            )
        )
        return result.scalar_one_or_none()

    async def list_matching_templates(
        self,
        *,
        workspace_id: UUID,
        bank_name: str | None = None,
        statement_type: str | None = None,
    ) -> list[MappingTemplateSnapshot]:
        if not bank_name and not statement_type:
            return []
        query = select(ImportMappingTemplate).where(
            ImportMappingTemplate.workspace_id == workspace_id
        )
        if bank_name:
            query = query.where(ImportMappingTemplate.bank_name == bank_name)
        if statement_type:
            query = query.where(ImportMappingTemplate.statement_type == statement_type)
        query = query.order_by(ImportMappingTemplate.updated_at.desc())
        result = await self.session.execute(query)
        return [
            _template_snapshot(template)
            for template in result.scalars().all()
            if template.column_mapping_json.get("kind") != "visual_coordinates"
        ]

    async def list_coordinate_templates(
        self,
        *,
        workspace_id: UUID,
        limit: int = 50,
    ) -> list[CoordinateTemplateSnapshot]:
        result = await self.session.execute(
            select(ImportMappingTemplate)
            .where(
                ImportMappingTemplate.workspace_id == workspace_id,
                ImportMappingTemplate.column_mapping_json["kind"].as_string()
                == "visual_coordinates",
            )
            .order_by(ImportMappingTemplate.updated_at.desc())
            .limit(limit)
        )
        templates = []
        for template in result.scalars().all():
            payload = template.column_mapping_json
            if payload.get("version") != 1 or not isinstance(payload.get("spec"), dict):
                raise ValueError("Unsupported visual coordinate template version.")
            templates.append(
                CoordinateTemplateSnapshot(
                    id=template.id,
                    name=template.name,
                    spec=CoordinateMappingSpec.model_validate(payload["spec"]),
                )
            )
        return templates

    async def create_coordinate_template(
        self,
        *,
        workspace_id: UUID,
        name: str,
        spec: CoordinateMappingSpec,
    ) -> CoordinateTemplateSnapshot:
        model = ImportMappingTemplate(
            workspace_id=workspace_id,
            name=name,
            bank_name=None,
            statement_type=None,
            default_currency=spec.default_currency,
            column_mapping_json={
                "kind": "visual_coordinates",
                "version": 1,
                "spec": spec.model_dump(mode="json"),
            },
        )
        self.session.add(model)
        await self.session.flush()
        return CoordinateTemplateSnapshot(id=model.id, name=model.name, spec=spec)


def _template_snapshot(template: ImportMappingTemplate) -> MappingTemplateSnapshot:
    column_mapping = template.column_mapping_json
    default_currency = column_mapping.get("default_currency") or template.default_currency
    table_signature = column_mapping.get("table_signature")
    return MappingTemplateSnapshot(
        id=template.id,
        name=template.name,
        bank_name=template.bank_name,
        statement_type=template.statement_type,
        default_currency=template.default_currency,
        mapping=StatementMappingSpec.model_validate(
            {
                **column_mapping,
                "default_currency": default_currency,
            }
        ),
        table_signature=(
            cast(dict[str, object], table_signature) if isinstance(table_signature, dict) else None
        ),
    )
