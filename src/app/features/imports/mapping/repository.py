from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.mapping.dto import (
    MappingTemplateSnapshot,
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
        default_currency: str,
        column_mapping: dict[str, object],
    ) -> MappingTemplateSnapshot:
        model = ImportMappingTemplate(
            workspace_id=workspace_id,
            name=name,
            bank_name=bank_name,
            statement_type=statement_type,
            default_currency=default_currency,
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
        return [_template_snapshot(template) for template in result.scalars().all()]


def _template_snapshot(template: ImportMappingTemplate) -> MappingTemplateSnapshot:
    return MappingTemplateSnapshot(
        id=template.id,
        name=template.name,
        bank_name=template.bank_name,
        statement_type=template.statement_type,
        default_currency=template.default_currency,
        column_mapping=template.column_mapping_json,
    )
